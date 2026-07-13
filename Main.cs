using System;
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

        public override void Save(UnityModManager.ModEntry modEntry)
        {
            Save(this, modEntry);
        }
    }

    public static class Main
    {
        private static string clipsDir;
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

            clipsDir = modPath + "\\clips\\";
            settings = UnityModManager.ModSettings.Load<Settings>(modEntry);
            LoadMappings();

            var harmony = new Harmony(modEntry.Info.Id);
            harmony.PatchAll(Assembly.GetExecutingAssembly());

            modEntry.OnToggle = (entry, value) => { Enabled = value; return true; };
            modEntry.OnUpdate = OnUpdate;
            modEntry.OnGUI = OnGui;
            modEntry.OnSaveGUI = (entry) => settings.Save(entry);

            return true;
        }

        private static int updateCount;

        private static void OnUpdate(UnityModManager.ModEntry modEntry, float delta)
        {
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
            GUILayout.EndVertical();
        }

        private static string lastTextValue = "";
        private static float lastTextTime;

        private static void LoadMappings()
        {
            // Scan clips for WAV files -> GUID list
            try
            {
                string[] files = System.IO.Directory.GetFiles(clipsDir, "*.wav");
                // Load ruRU.json
                string locPath = "C:\\Program Files (x86)\\Steam\\steamapps\\common\\Warhammer 40,000 Rogue Trader\\WH40KRT_Data\\StreamingAssets\\Localization\\ruRU.json";
                string json = System.IO.File.ReadAllText(locPath);
                var jObj = Newtonsoft.Json.Linq.JObject.Parse(json);
                var strings = jObj["strings"] as Newtonsoft.Json.Linq.JObject;

                foreach (string file in files)
                {
                    string guid = System.IO.Path.GetFileNameWithoutExtension(file);
                    if (guid.Length == 36 && strings != null)
                    {
                        var entry = strings[guid];
                        if (entry != null)
                        {
                            string text = entry["Text"].ToString();
                            if (text.Length > 3)
                                textMappings.Add(new KeyValuePair<string, string>(guid, text));
                        }
                    }
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

        public static void PlayClip(string guid)
        {
            if (!Enabled) return;
            string path = clipsDir + guid + ".wav";
            if (!System.IO.File.Exists(path)) return;

            mciSendString("close voice", null, 0, IntPtr.Zero);
            System.Threading.Thread.Sleep(10);

            string tmp = System.IO.Path.GetTempPath() + "rt_voice.wav";
            try { System.IO.File.Copy(path, tmp, true); }
            catch { return; }

            StringBuilder buf = new StringBuilder(256);
            int r = mciSendString("open \"" + tmp + "\" type waveaudio alias voice", buf, 256, IntPtr.Zero);
            if (r != 0) return;

            int vol = settings.Volume * 10;
            if (vol > 1000) vol = 1000;
            mciSendString("setaudio voice volume to " + vol, null, 0, IntPtr.Zero);
            mciSendString("play voice", null, 0, IntPtr.Zero);
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
