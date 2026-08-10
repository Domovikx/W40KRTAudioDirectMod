using System;
using System.Collections;
using System.Collections.Generic;
using System.IO;
using System.Reflection;
using System.Runtime.InteropServices;
using System.Text;
using UnityEngine;
using HarmonyLib;
using UnityModManagerNet;

namespace W40KRTAudioDirectMod
{
    public class Settings : UnityModManager.ModSettings
    {
        public int Volume = 100;
        public string Language = "ruRU";
        public int DuckLevel = 50;
        public bool MuteEnglishVoice = true;
        public bool VerboseDebugLog = false;
        public bool CollectSpeakerStats = false;
        public bool CollectUsageStats = false;

        public override void Save(UnityModManager.ModEntry modEntry)
        {
            Save(this, modEntry);
        }
    }

    public static class Main
    {
        private static string localizationDir;
        private static string modPath;
        private static Settings settings;
        private static List<KeyValuePair<string, string>> textMappings = new List<KeyValuePair<string, string>>();

        [DllImport("winmm.dll")]
        private static extern int mciSendString(string cmd, StringBuilder ret, int retLen, IntPtr hwnd);

        public static bool Enabled = true;

        static bool Load(UnityModManager.ModEntry modEntry)
        {
            modPath = Assembly.GetExecutingAssembly().Location;
            int idx = modPath.LastIndexOf('\\');
            if (idx > 0) modPath = modPath.Substring(0, idx);

            settings = UnityModManager.ModSettings.Load<Settings>(modEntry);
            localizationDir = modPath + "\\Localization\\" + settings.Language + "\\";
            InitTriggerLog();
            InitTracking();
            LoadMappings();

            var harmony = new Harmony(modEntry.Info.Id);
            harmony.PatchAll(Assembly.GetExecutingAssembly());

            // Patch BarkHandle ctor — единая точка создания барка с готовым текстом.
            // Озвучиваем барк ровно один раз здесь; экранные ре-рендеры того же текста
            // (овертипы, пан камеры) ловим в OnTextSet и пропускаем (BarkBlockView).
            Type barkHandle = AccessTools.TypeByName("Kingmaker.Code.UI.MVVM.VM.Bark.BarkHandle");
            if (barkHandle != null)
            {
                foreach (var c in barkHandle.GetConstructors(AccessTools.all))
                {
                    bool hasText = false;
                    foreach (var p in c.GetParameters())
                        if (p.Name == "text" && p.ParameterType == typeof(string)) { hasText = true; break; }
                    if (hasText) harmony.Patch(c, postfix: new HarmonyMethod(typeof(Main), "OnBarkCtorPostfix"));
                }
            }

            modEntry.OnToggle = (entry, value) => { Enabled = value; if (!value) { isPlaying = false; RestoreMusic(); FlushTracking(); } return true; };
            modEntry.OnUpdate = OnUpdate;
            modEntry.OnGUI = OnGui;
            modEntry.OnSaveGUI = (entry) => settings.Save(entry);

            return true;
        }

        private static int updateCount;
        private static bool isPlaying;
        private static StringBuilder mciStatusBuf = new StringBuilder(256);
        private static List<KeyValuePair<object, PropertyInfo>> duckProps = new List<KeyValuePair<object, PropertyInfo>>();
        private static int restoreFrames; // countdown: keep resetting RTPC after restore
        private static float[] savedVals;
        private static float[] savedRTPCVals;
        private static float[] rtpcOrigValues; // saved once at startup
        private static string duckLogPath;

        private static void LogDuck(string msg)
        {
            try { File.AppendAllText(duckLogPath, msg + "\n"); }
            catch { }
        }

        // Диагностика триггеров. Управляется через settings.VerboseDebugLog (UI-чекбокс).
        // Выключено по умолчанию. Для быстрого логирования: LogTrigger("...").
        private static bool TriggerLogEnabled { get { return settings != null && settings.VerboseDebugLog; } }
        private static string triggerLogPath;
        public static void InitTriggerLog()
        {
            if (!TriggerLogEnabled) return;
            try
            {
                triggerLogPath = modPath + "\\trigger_debug.log";
                File.WriteAllText(triggerLogPath, "=== W40KRT Audio Direct trigger log " + DateTime.Now.ToString("yyyy-MM-dd HH:mm:ss") + " ===\n");
            }
            catch { }
        }

        public static void LogTrigger(string msg)
        {
            if (!TriggerLogEnabled) return;
            try
            {
                if (triggerLogPath == null) triggerLogPath = modPath + "\\trigger_debug.log";
                File.AppendAllText(triggerLogPath, DateTime.Now.ToString("HH:mm:ss.fff") + " " + msg + "\n");
            }
            catch { }
        }

        // ── Статистика трекинга ──
        // speaker_stats.json: расхождения каталог vs игра
        // usage_stats.json: счётчики play/skip-cooldown/skip-bark/no-wav
        private static System.Text.RegularExpressions.Regex reGameSpeaker =
            new System.Text.RegularExpressions.Regex(@"^([\w\-\u0400-\u04FF]+[\w\-\s\u0400-\u04FF]*):\s*");
        private static System.Text.RegularExpressions.Regex reGuidFromPath =
            new System.Text.RegularExpressions.Regex(@"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12})");

        // in-memory accumulators — flush to disk every FLUSH_INTERVAL seconds
        private static Dictionary<string, object> speakerMismatches = new Dictionary<string, object>();
        private static Dictionary<string, Dictionary<string, int>> usageStats = new Dictionary<string, Dictionary<string, int>>();
        private static float lastFlushTime;
        private const float FLUSH_INTERVAL = 10f;
        private static string speakerStatsPath;
        private static string usageStatsPath;

        public static string ExtractGameSpeaker(string rawText)
        {
            if (string.IsNullOrEmpty(rawText)) return null;
            var m = reGameSpeaker.Match(rawText);
            return m.Success ? m.Groups[1].Value : null;
        }

        public static string ExtractGuidFromWav(string wavRelPath)
        {
            if (string.IsNullOrEmpty(wavRelPath)) return null;
            var m = reGuidFromPath.Match(wavRelPath);
            return m.Success ? m.Groups[1].Value : null;
        }

        private static void InitTracking()
        {
            speakerStatsPath = modPath + "\\speaker_stats.json";
            usageStatsPath = modPath + "\\usage_stats.json";
            speakerMismatches.Clear();
            usageStats.Clear();
            lastFlushTime = Time.time;
        }

        private static void TrackMismatchStats(string guid, string catalogSpeaker, string gameSpeaker, string text)
        {
            if (!settings.CollectSpeakerStats || string.IsNullOrEmpty(guid)) return;

            var key = guid;
            if (speakerMismatches.ContainsKey(key)) return; // already tracked this session

            var entry = new Dictionary<string, object> {
                { "catalog", catalogSpeaker ?? "" },
                { "game", gameSpeaker ?? "" },
                { "text", text ?? "" },
                { "count", 1 }
            };
            speakerMismatches[key] = entry;
            FlushTrackingIfNeeded();
        }

        private static void TrackUsageStats(string guid, string type)
        {
            if (!settings.CollectUsageStats || string.IsNullOrEmpty(guid)) return;

            if (!usageStats.ContainsKey(guid))
                usageStats[guid] = new Dictionary<string, int> { { "plays", 0 }, { "skips", 0 }, { "cooldown", 0 }, { "missing", 0 } };

            if (usageStats[guid].ContainsKey(type))
                usageStats[guid][type]++;

            FlushTrackingIfNeeded();
        }

        private static void FlushTrackingIfNeeded()
        {
            float now = Time.time;
            if (now - lastFlushTime < FLUSH_INTERVAL) return;
            FlushTracking();
        }

        public static void FlushTracking()
        {
            lastFlushTime = Time.time;

            if (settings.CollectSpeakerStats && speakerMismatches.Count > 0)
            {
                try
                {
                    var obj = new Dictionary<string, object> {
                        { "version", settings.GetType().GetField("Version") != null ? "" : "0.0.2" },
                        { "mismatches", speakerMismatches }
                    };
                    string json = Newtonsoft.Json.JsonConvert.SerializeObject(obj, Newtonsoft.Json.Formatting.Indented);
                    File.WriteAllText(speakerStatsPath, json);
                }
                catch { }
            }

            if (settings.CollectUsageStats && usageStats.Count > 0)
            {
                try
                {
                    var obj = new Dictionary<string, object> {
                        { "version", "0.0.2" },
                        { "entries", usageStats }
                    };
                    string json = Newtonsoft.Json.JsonConvert.SerializeObject(obj, Newtonsoft.Json.Formatting.Indented);
                    File.WriteAllText(usageStatsPath, json);
                }
                catch { }
            }
        }

        // ── Конец трекинга ──

        private static string Shorten(string s, int max = 80)
        {
            if (string.IsNullOrEmpty(s)) return s;
            s = s.Replace("\n", "\\n").Replace("\r", "\\r");
            return s.Length <= max ? s : s.Substring(0, max) + "...";
        }

        private static string EscapeLog(string s)
        {
            if (s == null) return "null";
            return s.Replace("\n", "\\n").Replace("\r", "\\r");
        }

        private static bool duckInitDone;
        private static void FindVolumeProps()
        {
            if (duckInitDone) return;
            if (duckLogPath == null)
            {
                duckLogPath = modPath + "\\duck_debug.log";
                try { File.WriteAllText(duckLogPath, "FindVolumeProps start\n"); }
                catch { }
            }
            try
            {
                // Find Kingmaker.Game.Instance (same approach as DialogCuePatch)
                Type gameType = null;
                foreach (Type t2 in AccessTools.AllTypes())
                    if (t2.FullName == "Kingmaker.Game") { gameType = t2; break; }
                object game = null;
                if (gameType != null)
                {
                    PropertyInfo gameInstP = gameType.GetProperty("Instance", BindingFlags.Public | BindingFlags.Static);
                    if (gameInstP != null) game = gameInstP.GetValue(null, null);
                }
                if (game == null)
                {
                    // Fallback: try GameSettingsController.Instance
                    Type gscType2 = AccessTools.TypeByName("Kingmaker.Settings.GameSettingsController");
                    if (gscType2 != null)
                    {
                        PropertyInfo gscInstP = gscType2.GetProperty("Instance");
                        if (gscInstP != null) game = gscInstP.GetValue(null, null);
                    }
                }
                if (game != null)
                {
                    LogDuck("Game type: " + game.GetType().FullName + " base: " + (game.GetType().BaseType != null ? game.GetType().BaseType.FullName : "null"));
                    // Dump ALL properties and fields of Game
                    for (var t = game.GetType(); t != null; t = t.BaseType)
                    {
                        foreach (var p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
                            LogDuck("  Game.prop(" + t.Name + "): " + p.Name + " : " + p.PropertyType.Name);
                        foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
                            LogDuck("  Game.field(" + t.Name + "): " + f.Name + " : " + f.FieldType.Name);
                    }
                    // try SoundSettingsController directly on Game
                    object ssc = GetPropOrField(game, "SoundSettingsController");
                    // try GameSettingsController -> SoundSettingsController
                    if (ssc == null)
                    {
                        object gsc = GetPropOrField(game, "GameSettingsController");
                        if (gsc != null)
                        {
                            LogDuck("GSC type: " + gsc.GetType().FullName);
                            ssc = GetPropOrField(gsc, "SoundSettingsController");
                            if (ssc != null) LogDuck("  Found SSC via GSC");
                        }
                    }
                    if (ssc != null)
                    {
                        LogDuck("SSC type: " + ssc.GetType().FullName);
                        for (var t = ssc.GetType(); t != null; t = t.BaseType)
                        {
                            foreach (var p in t.GetProperties(BindingFlags.Public | BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
                                LogDuck("  SSC.prop(" + t.Name + "): " + p.Name + " : " + p.PropertyType.Name);
                            foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
                                LogDuck("  SSC.field(" + t.Name + "): " + f.Name + " : " + f.FieldType.Name);
                        }
                        object ss = GetPropOrField(ssc, "Settings") ?? GetPropOrField(ssc, "m_Settings");
                        if (ss != null)
                        {
                            LogDuck("Settings type: " + ss.GetType().FullName);
                            for (var t = ss.GetType(); t != null; t = t.BaseType)
                            {
                                foreach (var f in t.GetFields(BindingFlags.Public | BindingFlags.Instance | BindingFlags.NonPublic | BindingFlags.DeclaredOnly))
                                {
                                    if (f.Name.Contains("Volume"))
                                        LogDuck("  volfield(" + t.Name + "): " + f.Name + " : " + f.FieldType.Name);
                                    if (!f.Name.Contains("Volume")) continue;
                                    Type ft = f.FieldType;
                                    PropertyInfo valProp = ft.GetProperty("Value", typeof(float));
                                    if (valProp != null && valProp.CanWrite)
                                    {
                                        var wrapper = new DuckFieldWrapper(ss, f, valProp);
                                        duckFieldWrappers.Add(wrapper);
                                        LogDuck("  -> FIELD duck: " + f.Name);
                                    }
                                }
                            }
                        }
                        else LogDuck("m_Settings is null on SSC");
                    }
                    else LogDuck("SoundSettingsController not found on Game (tried direct and via GSC)");
                }
                else LogDuck("Game instance (Kingmaker.Game/GameSettingsController) is null");

                // Try AudioMuteManager as fallback
                Type muteMgr = AccessTools.TypeByName("Kingmaker.Sound.AudioMuteManager");
                if (muteMgr == null) muteMgr = AccessTools.TypeByName("AudioMuteManager");
                if (muteMgr == null)
                {
                    foreach (Assembly a in AppDomain.CurrentDomain.GetAssemblies())
                    {
                        foreach (Type t in a.GetTypes())
                            if (t.Name == "AudioMuteManager") { muteMgr = t; break; }
                        if (muteMgr != null) break;
                    }
                }
                if (muteMgr != null)
                {
                    duckMuteSetAllState = muteMgr.GetMethod("SetAllAudioMuteState", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                    duckMuteNoneState = muteMgr.GetMethod("SetNoneState", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                    duckMuteSound = muteMgr.GetMethod("MuteSound", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                    duckMuteSetMusic = muteMgr.GetMethod("SetMusicMuteState", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                    LogDuck("AudioMuteManager found: SetAllAudioMuteState=" + (duckMuteSetAllState != null) + " SetNoneState=" + (duckMuteNoneState != null) + " MuteSound=" + (duckMuteSound != null) + " SetMusicMuteState=" + (duckMuteSetMusic != null));
                    duckMuteField = muteMgr.GetField("s_AllSoundMute", BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Static);
                    LogDuck("  s_AllSoundMute field: " + (duckMuteField != null));
                }

                LogDuck("Results: " + duckProps.Count + " props, " + duckWrappers.Count + " entity, " + duckFieldWrappers.Count + " field, " + duckEntityMethods.Count + " getEntity");

                // Try Wwise AkSoundEngine.SetRTPCValue(string, float)
                foreach (Assembly asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    string an = asm.GetName().Name;
                    if (an.IndexOf("Wwise", StringComparison.OrdinalIgnoreCase) < 0 &&
                        an.IndexOf("Ak", StringComparison.OrdinalIgnoreCase) < 0) continue;
                    Type akEngine = asm.GetType("AkSoundEngine");
                    if (akEngine == null)
                    {
                        foreach (Type t in asm.GetTypes())
                            if (t.Name == "AkSoundEngine") { akEngine = t; break; }
                    }
                    if (akEngine != null)
                    {
                        duckAkEngine = akEngine;
                        MethodInfo setRTPC = akEngine.GetMethod("SetRTPCValue", new Type[] { typeof(string), typeof(float) });
                        if (setRTPC != null)
                        {
                            duckSetRTPC = setRTPC;
                            LogDuck("Found AkSoundEngine.SetRTPCValue in " + an);
                        }
                        foreach (MethodInfo m in akEngine.GetMethods(BindingFlags.Public | BindingFlags.Static))
                        {
                            if (m.Name != "GetRTPCValue") continue;
                            ParameterInfo[] pi = m.GetParameters();
                            if (pi.Length >= 2 && pi[0].ParameterType == typeof(string))
                            {
                                duckGetRTPC = m;
                                LogDuck("Found AkSoundEngine.GetRTPCValue(string) in " + an);
                                break;
                            }
                        }
                        break;
                    }
                }

                bool hasSoundSettings = duckProps.Count > 0 || duckWrappers.Count > 0 || duckFieldWrappers.Count > 0
                    || duckEntityMethods.Count > 0;
                duckInitDone = hasSoundSettings;
                LogDuck("duckInitDone=" + duckInitDone + " (hasSoundSettings=" + hasSoundSettings + ")");
                // Save original RTPC values once at startup (before any ducking)
                if (duckGetRTPC != null && rtpcOrigValues == null)
                {
                    string[] names = { "MusicLevel", "DialogueLevel", "VoiceLevel", "SFXLevel", "AmbienceLevel", "AudioLevel" };
                    rtpcOrigValues = new float[names.Length];
                    for (int i = 0; i < names.Length; i++)
                    {
                        try
                        {
                            object[] getArgs = new object[] { names[i], 0, 0f, 0 };
                            duckGetRTPC.Invoke(null, getArgs);
                            rtpcOrigValues[i] = (float)getArgs[2];
                        }
                        catch (Exception ex) { rtpcOrigValues[i] = 100f; }
                    }
                    string origStr = "  Orig RTPC: ";
                    for (int i = 0; i < names.Length; i++)
                        origStr += names[i] + "=" + rtpcOrigValues[i].ToString("F2") + " ";
                    LogDuck(origStr);
                }
            }
            catch (Exception ex) { LogDuck("Error: " + ex.Message + "\n" + ex.StackTrace); duckInitDone = true; }
        }

        private static object GetPropOrField(object obj, string name)
        {
            if (obj == null) return null;
            Type t = obj.GetType();
            PropertyInfo p = t.GetProperty(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (p != null) return p.GetValue(obj, null);
            FieldInfo f = t.GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance);
            if (f != null) return f.GetValue(obj);
            // Check base types
            for (var bt = t.BaseType; bt != null; bt = bt.BaseType)
            {
                p = bt.GetProperty(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.DeclaredOnly);
                if (p != null) return p.GetValue(obj, null);
                f = bt.GetField(name, BindingFlags.Public | BindingFlags.NonPublic | BindingFlags.Instance | BindingFlags.DeclaredOnly);
                if (f != null) return f.GetValue(obj);
            }
            return null;
        }

        private static object GetProp(object obj, string name)
        {
            if (obj == null) return null;
            PropertyInfo p = obj.GetType().GetProperty(name);
            return p != null ? p.GetValue(obj, null) : null;
        }

        private static Type duckAkEngine;
        private static MethodInfo duckSetRTPC;
        private static MethodInfo duckGetRTPC;
        private static MethodInfo duckMuteSetAllState;
        private static MethodInfo duckMuteNoneState;
        private static MethodInfo duckMuteSound;
        private static MethodInfo duckMuteSetMusic;
        private static FieldInfo duckMuteField;

        private class DuckFieldWrapper
        {
            public object target;
            public FieldInfo entityField;
            public PropertyInfo valProp;
            public DuckFieldWrapper(object t, FieldInfo ef, PropertyInfo vp)
            { target = t; entityField = ef; valProp = vp; }
            public object Entity { get { return entityField.GetValue(target); } }
            public float Value { get { return (float)valProp.GetValue(Entity, null); } set { valProp.SetValue(Entity, value, null); } }
        }
        private static List<DuckFieldWrapper> duckFieldWrappers = new List<DuckFieldWrapper>();

        private class DuckEntityGetter
        {
            public string key;
            public object entity;
            public PropertyInfo valProp;
            public DuckEntityGetter(string k, object e, PropertyInfo vp)
            { key = k; entity = e; valProp = vp; }
            public float Value { get { return (float)valProp.GetValue(entity, null); } set { valProp.SetValue(entity, value, null); } }
        }
        private static List<DuckEntityGetter> duckEntityMethods = new List<DuckEntityGetter>();

        private class DuckPropWrapper
        {
            public object target;
            public PropertyInfo entityProp;
            public PropertyInfo valProp;
            public DuckPropWrapper(object t, PropertyInfo ep, PropertyInfo vp)
            { target = t; entityProp = ep; valProp = vp; }
            public object Entity { get { return entityProp.GetValue(target, null); } }
            public float Value { get { return (float)valProp.GetValue(Entity, null); } set { valProp.SetValue(Entity, value, null); } }
        }
        private static List<DuckPropWrapper> duckWrappers = new List<DuckPropWrapper>();

        private static void DuckMusic()
        {
            if (settings.DuckLevel == 0) return;
            if (savedVals != null) return;
            float mul = settings.DuckLevel / 100f;
            FindVolumeProps();
            List<float> vals = new List<float>();
            try
            {
                foreach (var kv in duckProps)
                {
                    vals.Add((float)kv.Value.GetValue(kv.Key, null));
                    kv.Value.SetValue(kv.Key, vals[vals.Count - 1] * mul, null);
                }
                foreach (var w in duckWrappers)
                {
                    vals.Add(w.Value);
                    w.Value = vals[vals.Count - 1] * mul;
                }
                foreach (var w in duckFieldWrappers)
                {
                    vals.Add(w.Value);
                    w.Value = vals[vals.Count - 1] * mul;
                }
                foreach (var e in duckEntityMethods)
                {
                    vals.Add(e.Value);
                    e.Value = vals[vals.Count - 1] * mul;
                }
            }
            catch { }
            if (duckSetRTPC != null)
            {
                string[] rtpcNames = { "MusicLevel", "DialogueLevel", "VoiceLevel", "SFXLevel", "AmbienceLevel", "AudioLevel" };
                // Save original RTPC values if GetRTPCValue is available
                if (duckGetRTPC != null)
                {
                    savedRTPCVals = new float[rtpcNames.Length];
                    for (int i = 0; i < rtpcNames.Length; i++)
                    {
                        try
                        {
                            object[] getArgs = new object[] { rtpcNames[i], 0, 0f, 0 };
                            duckGetRTPC.Invoke(null, getArgs);
                            savedRTPCVals[i] = (float)getArgs[2];
                        }
                        catch (Exception ex) { LogDuck("  GetRTPC err " + rtpcNames[i] + ": " + ex.Message); savedRTPCVals[i] = 100f; }
                    }
                    LogDuck("  Saved RTPC: " + string.Join(", ", Array.ConvertAll(savedRTPCVals, v => v.ToString("F2"))));
                }
                float[] curDucked = new float[rtpcNames.Length];
                for (int i = 0; i < rtpcNames.Length; i++)
                {
                    try
                    {
                        string name = rtpcNames[i];
                        float baseVal = (savedRTPCVals != null && i < savedRTPCVals.Length) ? savedRTPCVals[i] : 100f;
                        float target;
                        if (settings.MuteEnglishVoice && (name == "VoiceLevel" || name == "DialogueLevel"))
                        {
                            if (savedVoiceRTPC == null) savedVoiceRTPC = new float[2];
                            int vi = (name == "VoiceLevel") ? 0 : 1;
                            if (savedVoiceRTPC[vi] == 0f) savedVoiceRTPC[vi] = baseVal;
                            target = 0f;
                            LogDuck("  Voice mute: " + name + " = 0");
                        }
                        else
                        {
                            target = baseVal * mul;
                        }
                        curDucked[i] = target;
                        duckSetRTPC.Invoke(null, new object[] { name, target });
                    }
                    catch (Exception ex) { LogDuck("  RTPC err " + rtpcNames[i] + ": " + ex.Message); }
                }
                duckedRTPC = curDucked;
            }
            savedVals = vals.ToArray();
            restoreFrames = 0;
            LogDuck("DuckMusic: saved " + savedVals.Length + " values, mul=" + mul);
        }

        private static string[] rtpcNames = { "MusicLevel", "DialogueLevel", "VoiceLevel", "SFXLevel", "AmbienceLevel", "AudioLevel" };
        private static float[] savedVoiceRTPC;
        private static float[] duckedRTPC;
        private static int fadeFramesRemaining; // smooth restore countdown
        private static float[] fadeStartVals; // RTPC values at fade start (ducked)
        private static float[] fadeTargetVals; // RTPC values to reach (original)

        private static void RestoreMusic()
        {
            if (savedVals == null) return;
            try
            {
                int c = 0;
                foreach (var kv in duckProps)
                    kv.Value.SetValue(kv.Key, savedVals[c++], null);
                foreach (var w in duckWrappers)
                    w.Value = savedVals[c++];
                foreach (var w in duckFieldWrappers)
                    w.Value = savedVals[c++];
                foreach (var e in duckEntityMethods)
                    e.Value = savedVals[c++];
            }
            catch { }
            // Restore State FIRST (Wwise State resets internal RTPC curves)
            if (duckMuteNoneState != null)
            {
                try { duckMuteNoneState.Invoke(null, null); LogDuck("  SetNoneState()"); }
                catch (Exception ex) { LogDuck("  SetNoneState err: " + ex.Message); }
            }
            // Smooth RTPC restore: save target values, start fade
            if (duckSetRTPC != null && duckedRTPC != null)
            {
                fadeTargetVals = new float[rtpcNames.Length];
                for (int i = 0; i < rtpcNames.Length; i++)
                {
                    string name = rtpcNames[i];
                    if (savedVoiceRTPC != null && name == "VoiceLevel") fadeTargetVals[i] = savedVoiceRTPC[0];
                    else if (savedVoiceRTPC != null && name == "DialogueLevel") fadeTargetVals[i] = savedVoiceRTPC[1];
                    else fadeTargetVals[i] = (savedRTPCVals != null && i < savedRTPCVals.Length) ? savedRTPCVals[i] : 100f;
                }
                fadeStartVals = (float[])duckedRTPC.Clone();
                fadeFramesRemaining = 20; // ~330ms at 60fps
            }
            else if (duckSetRTPC != null)
            {
                // No ducked values saved — instant restore
                for (int i = 0; i < rtpcNames.Length; i++)
                {
                    float restoreVal = (savedRTPCVals != null && i < savedRTPCVals.Length) ? savedRTPCVals[i] : 100f;
                    try { duckSetRTPC.Invoke(null, new object[] { rtpcNames[i], restoreVal }); }
                    catch { }
                }
            }
            if (duckMuteField != null && savedVals.Length == 0)
            {
                try { duckMuteField.SetValue(null, false); LogDuck("  s_AllSoundMute=false"); }
                catch (Exception ex) { LogDuck("  s_AllSoundMute restore err: " + ex.Message); }
            }
            savedVals = null;
            savedRTPCVals = null;
            savedVoiceRTPC = null;
            if (fadeFramesRemaining == 0)
                restoreFrames = 60; // no fade needed — start persistent restore
            LogDuck("RestoreMusic (fade=" + fadeFramesRemaining + " frames, then restoreFrames=60)");
        }

        private static void OnUpdate(UnityModManager.ModEntry modEntry, float delta)
        {
            FlushTrackingIfNeeded();

            if (isPlaying)
            {
                mciStatusBuf.Clear();
                mciSendString("status voice mode", mciStatusBuf, 256, IntPtr.Zero);
                if (mciStatusBuf.ToString() != "playing")
                {
                    isPlaying = false;
                    RestoreMusic();
                }
            }

            if (fadeFramesRemaining > 0 && duckSetRTPC != null && fadeStartVals != null && fadeTargetVals != null)
            {
                fadeFramesRemaining--;
                float t = 1f - (float)fadeFramesRemaining / 20f; // 0→1 over 20 frames
                for (int i = 0; i < rtpcNames.Length && i < fadeStartVals.Length && i < fadeTargetVals.Length; i++)
                {
                    float val = fadeStartVals[i] + (fadeTargetVals[i] - fadeStartVals[i]) * t;
                    try { duckSetRTPC.Invoke(null, new object[] { rtpcNames[i], val }); }
                    catch { }
                }
                if (fadeFramesRemaining == 0)
                {
                    LogDuck("Smooth fade done, starting persistent restore");
                    restoreFrames = 60;
                }
            }
            else if (restoreFrames > 0)
            {
                restoreFrames--;
                if (restoreFrames == 59) LogDuck("PersistentRestore start");
                if (duckMuteNoneState != null)
                {
                    try { duckMuteNoneState.Invoke(null, null); }
                    catch { }
                }
                if (duckSetRTPC != null)
                {
                    for (int i = 0; i < rtpcNames.Length; i++)
                    {
                        float val = (fadeTargetVals != null && i < fadeTargetVals.Length) ? fadeTargetVals[i] : 100f;
                        try { duckSetRTPC.Invoke(null, new object[] { rtpcNames[i], val }); }
                        catch { }
                    }
                }
                if (duckMuteField != null)
                {
                    try { duckMuteField.SetValue(null, false); }
                    catch { }
                }
                if (restoreFrames == 0) LogDuck("PersistentRestore end");
            }

            updateCount++;
            if (updateCount == 1)
            {
                try
                {
                    Type tmpType = Type.GetType("TMPro.TextMeshProUGUI, Unity.TextMeshPro");
                    if (tmpType == null)
                    {
                        foreach (Assembly a in AppDomain.CurrentDomain.GetAssemblies())
                            if (a.GetName().Name == "Unity.TextMeshPro")
                            { tmpType = a.GetType("TMPro.TextMeshProUGUI"); break; }
                    }
                    if (tmpType != null && tmpType.BaseType != null)
                    {
                        var setText = tmpType.BaseType.GetMethod("set_text", new Type[] { typeof(string) });
                        if (setText != null)
                            new Harmony("W40KRTAudioDirectMod.TMP").Patch(setText,
                                prefix: new HarmonyMethod(typeof(Main), "OnTextSet"));
                    }
                }
                catch { }
            }
        }

        private static void OnGui(UnityModManager.ModEntry modEntry)
        {
            GUILayout.BeginVertical();
            GUILayout.Label("W40KRT Audio Direct Mod", GUILayout.ExpandWidth(true));

            GUILayout.Space(5f);
            GUILayout.Label("Громкость озвучки:");
            int vol = (int)GUILayout.HorizontalSlider((float)settings.Volume, 0f, 100f, GUILayout.Width(200f));
            if (vol != settings.Volume)
            {
                settings.Volume = vol;
                settings.Save(modEntry);
            }
            GUILayout.Label("  " + settings.Volume + "%");

            GUILayout.Space(10f);
            GUILayout.Label("Приглушение игры на время озвучки:");
            GUILayout.BeginHorizontal();
            GUILayout.Label("0 (выкл)", GUILayout.Width(60f));
            int dl = (int)GUILayout.HorizontalSlider((float)settings.DuckLevel, 0f, 100f, GUILayout.Width(200f));
            GUILayout.Label("100 (полн.)", GUILayout.Width(80f));
            GUILayout.Label("= " + settings.DuckLevel + "%", GUILayout.Width(60f));
            GUILayout.EndHorizontal();
            if (dl != settings.DuckLevel)
            {
                settings.DuckLevel = dl;
                settings.Save(modEntry);
            }

            bool mute = GUILayout.Toggle(settings.MuteEnglishVoice, new GUIContent(
                "Отключать английскую озвучку",
                "Когда включено: оригинальные голоса персонажей не слышны одновременно с нашей озвучкой.\nКогда выключено: английские голоса играют фоном (приглушаются только музыка и SFX)."
            ));
            if (mute != settings.MuteEnglishVoice)
            {
                settings.MuteEnglishVoice = mute;
                settings.Save(modEntry);
            }
            GUILayout.Label("  Если включено — английские голоса замолкают на время нашей реплики.\n  Если выключено — слышны и наши, и английские голоса одновременно.", GUILayout.Width(350f));

            GUILayout.Space(10f);
            GUILayout.Label("Загружено WAV: " + textMappings.Count);

            GUILayout.Space(10f);
            GUILayout.Label("Диагностика и улучшение озвучки", GUILayout.ExpandWidth(true));
            GUILayout.Label("Все настройки ниже выключены по умолчанию. Они не влияют на озвучку,", GUILayout.Width(350f));
            GUILayout.Label("а только собирают данные для её улучшения. Файлы лежат в папке мода.", GUILayout.Width(350f));

            bool verbose = GUILayout.Toggle(settings.VerboseDebugLog, new GUIContent(
                "Подробный лог срабатываний (trigger_debug.log)",
                "Записывает какие фразы игра пыталась озвучить, какие WAV проигрались. Включите перед отправкой баг-репорта."
            ));
            if (verbose != settings.VerboseDebugLog)
            {
                settings.VerboseDebugLog = verbose;
                if (verbose) InitTriggerLog();
                settings.Save(modEntry);
            }

            bool spkStats = GUILayout.Toggle(settings.CollectSpeakerStats, new GUIContent(
                "Статистика расхождений спикеров (speaker_stats.json)",
                "Сверяет кого игра считает говорящим с тем что записано в каталоге мода. Помогает исправлять ошибки в определении персонажей."
            ));
            if (spkStats != settings.CollectSpeakerStats)
            {
                settings.CollectSpeakerStats = spkStats;
                settings.Save(modEntry);
            }

            bool usageStats = GUILayout.Toggle(settings.CollectUsageStats, new GUIContent(
                "Статистика использования (usage_stats.json)",
                "Считает сколько раз фразы проигрались, сколько пропущены по кулдауну или из-за отсутствия WAV. Помогает понять что озвучить в первую очередь."
            ));
            if (usageStats != settings.CollectUsageStats)
            {
                settings.CollectUsageStats = usageStats;
                settings.Save(modEntry);
            }

            GUILayout.EndVertical();
        }

        private static Dictionary<string, float> lastPlayedByKey = new Dictionary<string, float>();
        private const float GUID_COOLDOWN = 10f;

        private static readonly System.Text.RegularExpressions.Regex normTmpTag =
            new System.Text.RegularExpressions.Regex(@"<[^>]*>");
        private static readonly System.Text.RegularExpressions.Regex normMarkup =
            new System.Text.RegularExpressions.Regex(@"\{/?[a-zA-Z_]+\|[^}]*\}|\{/?[a-zA-Z_]+\}");
        private static readonly System.Text.RegularExpressions.Regex normOuterQuotes =
            new System.Text.RegularExpressions.Regex(@"^\s*([""\u00ab\u201c\u201e])(.*?)([\u00bb\u201d\u201c""])\s*(\.?)\s*$");
        private static readonly System.Text.RegularExpressions.Regex normWs =
            new System.Text.RegularExpressions.Regex(@"\s+");

        private static readonly System.Text.RegularExpressions.Regex normSpeakerPrefix =
            new System.Text.RegularExpressions.Regex(@"^[^:]+:\s*");

        public static string NormalizeText(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            s = normTmpTag.Replace(s, "");       // <align="center"> etc.
            s = normMarkup.Replace(s, "");       // {n} {/n} {g|...}{/g} {mf|a|b} {name}
            s = normSpeakerPrefix.Replace(s, "");  // Kunrad Voigtvir: "текст" -> "текст"
            s = normOuterQuotes.Replace(s, "$2$4"); // "Текст". / «Текст».
            s = normWs.Replace(s, " ").Trim();
            return s;
        }

        private static void LoadMappings()
        {
            textMappings.Clear();
            localizationDir = modPath + "\\Localization\\" + settings.Language + "\\";

            try
            {
                // Split mappings: Localization/{lang}/mappings/*.json — per character file
                string mapsDir = localizationDir + "mappings";
                if (Directory.Exists(mapsDir))
                {
                    var files = Directory.GetFiles(mapsDir, "*.json");
                    Array.Sort(files, StringComparer.Ordinal);
                    foreach (string f in files)
                        LoadMappingsFile(f);
                    return;
                }

                // Legacy single-file fallback (mappings.json)
                LoadMappingsFile(localizationDir + "mappings.json");
            }
            catch { }
        }

        private static void LoadMappingsFile(string jsonPath)
        {
            if (!File.Exists(jsonPath)) return;

            var jObj = Newtonsoft.Json.Linq.JObject.Parse(File.ReadAllText(jsonPath));
            var entries = jObj["entries"] as Newtonsoft.Json.Linq.JArray;
            if (entries == null) return;

            foreach (var e in entries)
            {
                string t = e["t"] != null ? e["t"].ToString() : null;
                string w = e["w"] != null ? e["w"].ToString() : null;
                if (string.IsNullOrEmpty(t) || string.IsNullOrEmpty(w)) continue;
                textMappings.Add(new KeyValuePair<string, string>(w, t));
            }
        }

        public static void OnBarkCtorPostfix(string text)
        {
            if (!Enabled || string.IsNullOrEmpty(text)) return;
            HandleBark(text);
        }

        public static void HandleBark(string text)
        {
            if (!Enabled || string.IsNullOrEmpty(text)) return;
            string n = NormalizeText(text);
            if (n.Length == 0) return;

            LogTrigger("BARK full-value: " + EscapeLog(text));

            float now = Time.time;
            for (int i = 0; i < textMappings.Count; i++)
            {
                if (textMappings[i].Value != n) continue;

                string wav = textMappings[i].Key;

                float lastT;
                if (lastPlayedByKey.TryGetValue(wav, out lastT) && now - lastT < GUID_COOLDOWN)
                {
                    LogTrigger("BARK skip-cooldown wav=" + wav + " text=" + Shorten(text));
                    return;
                }

                lastPlayedByKey[wav] = now;
                LogTrigger("BARK play wav=" + wav + " text=" + Shorten(text));
                PlayClip(wav);
                return;
            }
        }

        public static void OnTextSet(string value)
        {
            if (!Enabled) return;
            if (value == null || value.Length <= 3) return;

            string n = NormalizeText(value);
            if (n.Length == 0) return;

            LogTrigger("TEXT full-value: " + EscapeLog(value));

            float now = Time.time;
            for (int i = 0; i < textMappings.Count; i++)
            {
                if (textMappings[i].Value != n) continue;

                string wav = textMappings[i].Key;
                var stack = Environment.StackTrace;

                // Барк-текст (BarkBlockView) — озвучивается ровно один раз при создании
                // барка через BarkHandle..ctor (HandleBark). Повторные установки того же
                // текста (овертипы при пане камеры, ре-рендеры) здесь пропускаем.
                if (stack.Contains("BarkBlockView"))
                {
                    LogTrigger("TEXT skip-barkdisplay wav=" + wav);
                    TrackUsageStats(ExtractGuidFromWav(wav), "skips");
                    break;
                }

                float lastT;
                if (lastPlayedByKey.TryGetValue(wav, out lastT) && now - lastT < GUID_COOLDOWN)
                {
                    LogTrigger("TEXT skip-cooldown wav=" + wav);
                    TrackUsageStats(ExtractGuidFromWav(wav), "cooldown");
                    return;
                }

                lastPlayedByKey[wav] = now;
                LogTrigger("TEXT play wav=" + wav);
                TrackUsageStats(ExtractGuidFromWav(wav), "plays");

                // Check speaker mismatch
                if (settings.CollectSpeakerStats)
                {
                    string gameSpk = ExtractGameSpeaker(value);
                    if (!string.IsNullOrEmpty(gameSpk))
                    {
                        string guid = ExtractGuidFromWav(wav);
                        TrackMismatchStats(guid, null, gameSpk, n);
                    }
                }

                PlayClip(wav);
                return;
            }
        }

        public static void PlayClip(string pathOrGuid)
        {
            if (!Enabled) return;
            string path = null;

            // Relative wav path from mappings.json ("Npc/guid.wav")
            if (pathOrGuid.IndexOf('\\') >= 0 || pathOrGuid.IndexOf('/') >= 0)
            {
                string full = localizationDir + pathOrGuid;
                if (File.Exists(full)) path = full;
            }
            else
            {
                // GUID key (dialog cue): resolve in localization tree
                string full = localizationDir + pathOrGuid + ".wav";
                if (File.Exists(full)) path = full;
                else
                {
                    var found = Directory.GetFiles(localizationDir, pathOrGuid + ".wav", SearchOption.AllDirectories);
                    if (found.Length > 0) path = found[0];
                }
            }
            if (path == null || !File.Exists(path)) return;

            mciSendString("close voice", null, 0, IntPtr.Zero);
            System.Threading.Thread.Sleep(10);

            string tmp = System.IO.Path.GetTempPath() + "rt_voice.wav";
            try { File.Copy(path, tmp, true); }
            catch { return; }

            StringBuilder buf = new StringBuilder(256);
            int r = mciSendString("open \"" + tmp + "\" type waveaudio alias voice", buf, 256, IntPtr.Zero);
            if (r != 0) return;

            int vol = settings.Volume * 10;
            if (vol > 1000) vol = 1000;
            mciSendString("setaudio voice volume to " + vol, null, 0, IntPtr.Zero);
            mciSendString("play voice", null, 0, IntPtr.Zero);

            isPlaying = true;
            DuckMusic();
        }
    }
    [HarmonyPatch("Kingmaker.Code.UI.MVVM.VM.Dialog.Dialog.DialogVM", "HandleOnCueShow")]
    public static class DialogCuePatch
    {
        private static bool tried;
        private static PropertyInfo instanceP;

        [HarmonyPostfix]
        public static void Postfix()
        {
            if (!Main.Enabled) return;
            try
            {
                if (!tried)
                {
                    tried = true;
                    foreach (Type t in AccessTools.AllTypes())
                        if (t.FullName == "Kingmaker.Game")
                        { instanceP = t.GetProperty("Instance", BindingFlags.Public | BindingFlags.Static); break; }
                }
                if (instanceP == null) return;
                object gi = instanceP.GetValue(null, null);
                if (gi == null) return;

                object dc = null;
                foreach (var p in gi.GetType().GetProperties())
                    if (p.Name.ToLower().Contains("dialog")) { dc = p.GetValue(gi, null); break; }
                if (dc == null)
                    foreach (var f in gi.GetType().GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
                        if (f.Name.ToLower().Contains("dialog")) { dc = f.GetValue(gi); break; }
                if (dc == null) return;

                var cueP = dc.GetType().GetProperty("CurrentCue");
                if (cueP == null) return;
                object cue = cueP.GetValue(dc, null);
                if (cue == null) return;

                var textP = cue.GetType().GetProperty("LocalizedStringText");
                if (textP == null) textP = cue.GetType().GetProperty("DisplayText");
                if (textP == null) return;
                object txt = textP.GetValue(cue, null);
                if (txt == null) return;

                var keyP = txt.GetType().GetProperty("Key");
                string k = keyP != null ? (string)keyP.GetValue(txt, null) : null;
                if (!string.IsNullOrEmpty(k))
                {
                    Main.LogTrigger("DIALOG cue guid=" + k);
                    Main.PlayClip(k);
                }
            }
            catch { }
        }
    }
}
