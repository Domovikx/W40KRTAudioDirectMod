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
        public bool DuckMusic = true;
        public int DuckLevel = 0;

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
            LoadMappings();

            var harmony = new Harmony(modEntry.Info.Id);
            harmony.PatchAll(Assembly.GetExecutingAssembly());

            modEntry.OnToggle = (entry, value) => { Enabled = value; if (!value) { isPlaying = false; RestoreMusic(); } return true; };
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
            if (!settings.DuckMusic) return;
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
                foreach (string r in rtpcNames)
                {
                    try
                    {
                        duckSetRTPC.Invoke(null, new object[] { r, mul });
                        LogDuck("  RTPC: " + r + " = " + mul);
                    }
                    catch (Exception ex) { LogDuck("  RTPC err " + r + ": " + ex.Message); }
                }
            }
            savedVals = vals.ToArray();
            restoreFrames = 0;
            LogDuck("DuckMusic: saved " + savedVals.Length + " values, mul=" + mul);
        }

        private static string[] rtpcNames = { "MusicLevel", "DialogueLevel", "VoiceLevel", "SFXLevel", "AmbienceLevel", "AudioLevel" };

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
            if (duckSetRTPC != null)
            {
                string[] rtpcNames = { "MusicLevel", "DialogueLevel", "VoiceLevel", "SFXLevel", "AmbienceLevel", "AudioLevel" };
                for (int i = 0; i < rtpcNames.Length; i++)
                {
                    float restoreVal = (savedRTPCVals != null && i < savedRTPCVals.Length) ? savedRTPCVals[i] : 100f;
                    try
                    {
                        duckSetRTPC.Invoke(null, new object[] { rtpcNames[i], restoreVal });
                        LogDuck("  RTPC restore: " + rtpcNames[i] + " = " + restoreVal.ToString("F2"));
                    }
                    catch (Exception ex) { LogDuck("  RTPC restore err " + rtpcNames[i] + ": " + ex.Message); }
                }
            }
            if (duckMuteField != null && savedVals.Length == 0)
            {
                try { duckMuteField.SetValue(null, false); LogDuck("  s_AllSoundMute=false"); }
                catch (Exception ex) { LogDuck("  s_AllSoundMute restore err: " + ex.Message); }
            }
            savedVals = null;
            savedRTPCVals = null;
            restoreFrames = 60;
            LogDuck("RestoreMusic (restoreFrames=60)");
        }

        private static void OnUpdate(UnityModManager.ModEntry modEntry, float delta)
        {
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

            if (restoreFrames > 0)
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
                    string[] rtpcNames = { "MusicLevel", "DialogueLevel", "VoiceLevel", "SFXLevel", "AmbienceLevel", "AudioLevel" };
                    for (int i = 0; i < rtpcNames.Length; i++)
                    {
                        float val = (savedRTPCVals != null && i < savedRTPCVals.Length) ? savedRTPCVals[i] : 100f;
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

            int v = (int)GUILayout.HorizontalSlider((float)settings.Volume, 0f, 100f, GUILayout.Width(200f));
            if (v != settings.Volume)
            {
                settings.Volume = v;
                settings.Save(modEntry);
            }
            GUILayout.Label("Громкость: " + settings.Volume + "%");

            GUILayout.Space(5f);
            bool duck = GUILayout.Toggle(settings.DuckMusic, new GUIContent("Приглушать музыку", "Автоматически убавлять громкость музыки в игре пока звучит наша озвучка. Громкость восстанавливается после окончания реплики."), GUILayout.ExpandWidth(true));
            if (duck != settings.DuckMusic)
            {
                settings.DuckMusic = duck;
                settings.Save(modEntry);
            }
            if (settings.DuckMusic)
            {
                GUILayout.BeginHorizontal();
                GUILayout.Space(30f);
                GUILayout.Label("Громкость музыки:", GUILayout.Width(130f));
                int dl = (int)GUILayout.HorizontalSlider((float)settings.DuckLevel, 0f, 100f, GUILayout.Width(150f));
                if (dl != settings.DuckLevel)
                {
                    settings.DuckLevel = dl;
                    settings.Save(modEntry);
                }
                GUILayout.Label(dl + "%", GUILayout.Width(30f));
                GUILayout.EndHorizontal();
            }

            GUILayout.Space(10f);
            GUILayout.BeginHorizontal();
            GUILayout.Label("Язык:", GUILayout.Width(50f));
            string lang = GUILayout.TextField(settings.Language, GUILayout.Width(80f));
            if (lang != settings.Language && lang.Length > 0)
            {
                settings.Language = lang;
                settings.Save(modEntry);
localizationDir = modPath + "\\Localization\\" + settings.Language + "\\";
                LoadMappings();
            }
            if (GUILayout.Button("Reload", GUILayout.Width(60f)))
            {
                LoadMappings();
            }
            GUILayout.EndHorizontal();
            GUILayout.Label("Доступные: ruRU, enGB, deDE, frFR, esES, jaJP, zhCN, trTR", GUILayout.ExpandWidth(true));
            GUILayout.Label("WAV: " + textMappings.Count, GUILayout.ExpandWidth(true));

            GUILayout.EndVertical();
        }

        private static string lastTextValue = "";
        private static float lastTextTime;

        private static void LoadMappings()
        {
            textMappings.Clear();
            localizationDir = modPath + "\\Localization\\" + settings.Language + "\\";

            try
            {
                if (!Directory.Exists(localizationDir)) return;

                string[] files = Directory.GetFiles(localizationDir, "*.wav", SearchOption.AllDirectories);
                if (files.Length == 0) return;

                string gameLocalizationPath = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Warhammer 40,000 Rogue Trader\\WH40KRT_Data\\StreamingAssets\\Localization\\";
                string jsonPath = gameLocalizationPath + settings.Language + ".json";
                if (!File.Exists(jsonPath)) return;

                string json = File.ReadAllText(jsonPath);
                var jObj = Newtonsoft.Json.Linq.JObject.Parse(json);
                var strings = jObj["strings"] as Newtonsoft.Json.Linq.JObject;
                if (strings == null) return;

                foreach (string file in files)
                {
                    string guid = Path.GetFileNameWithoutExtension(file);
                    if (guid.Length != 36) continue;

                    var entry = strings[guid];
                    if (entry == null) continue;

                    string text = entry["Text"].ToString();
                    if (text.Length > 3)
                        textMappings.Add(new KeyValuePair<string, string>(file, text));
                }
            }
            catch { }
        }

        public static void OnTextSet(string value)
        {
            if (!Enabled) return;
            if (value == null || value.Length <= 3) return;

            float now = Time.time;
            if (value == lastTextValue && now - lastTextTime < 2f) return;
            lastTextValue = value;
            lastTextTime = now;

            for (int i = 0; i < textMappings.Count; i++)
            {
                if (value.IndexOf(textMappings[i].Value) >= 0)
                {
                    PlayClip(textMappings[i].Key);
                    return;
                }
            }
        }

        public static void PlayClip(string pathOrGuid)
        {
            if (!Enabled) return;
            string path = pathOrGuid;
            if (!File.Exists(path))
            {
                string full = localizationDir + pathOrGuid + ".wav";
                if (File.Exists(full)) path = full;
                else
                {
                    var found = Directory.GetFiles(localizationDir, pathOrGuid + ".wav", SearchOption.AllDirectories);
                    if (found.Length == 0) return;
                    path = found[0];
                }
            }
            if (!File.Exists(path)) return;

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
                if (!string.IsNullOrEmpty(k)) Main.PlayClip(k);
            }
            catch { }
        }
    }
}
