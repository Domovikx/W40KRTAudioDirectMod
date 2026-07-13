using System;
using System.Collections.Generic;
using System.Reflection;
using System.Runtime.InteropServices;
using HarmonyLib;
using UnityModManagerNet;

namespace W40KRTAudioDirectMod
{
    public static class Main
    {
        private static Dictionary<string, string> guidToWav = new Dictionary<string, string>();
        private static bool played36;

        [DllImport("winmm.dll", SetLastError = true)]
        private static extern bool PlaySound(string pszSound, IntPtr hmod, uint fdwSound);

        private const uint SND_FILENAME = 0x00020000;
        private const uint SND_ASYNC = 0x0001;

        public static bool Enabled = true;

        static bool Load(UnityModManager.ModEntry modEntry)
        {
            string modPath = Assembly.GetExecutingAssembly().Location;
            int idx = modPath.LastIndexOf('\\');
            if (idx > 0) modPath = modPath.Substring(0, idx);

            string clipsDir = modPath + "\\clips\\";
            guidToWav["93eaeadd-6adb-47aa-af0d-45e37840a92d"] = clipsDir + "93eaeadd-6adb-47aa-af0d-45e37840a92d.wav";
            guidToWav["36a60f39-1962-464e-8bdc-ea78e5559370"] = clipsDir + "36a60f39-1962-464e-8bdc-ea78e5559370.wav";
            guidToWav["7d7fdde5-2ea2-4194-b0c5-b1b672268fbc"] = clipsDir + "7d7fdde5-2ea2-4194-b0c5-b1b672268fbc.wav";
            guidToWav["9e22eda7-5e0c-4bd0-aff6-5e535872b847"] = clipsDir + "9e22eda7-5e0c-4bd0-aff6-5e535872b847.wav";

            var harmony = new Harmony(modEntry.Info.Id);
            harmony.PatchAll(Assembly.GetExecutingAssembly());

            modEntry.OnToggle = (entry, value) => { Enabled = value; return true; };
            modEntry.OnUpdate = OnUpdate;

            return true;
        }

        private static int updateCount;

        private static void OnUpdate(UnityModManager.ModEntry modEntry, float delta)
        {
            updateCount++;
            if (updateCount == 1)
            {
                UnityEngine.Debug.Log("[W40KRTAudioDirectMod] OnUpdate first frame");
                try
                {
                    // Try Type.GetType first
                    Type tmpType = Type.GetType("TMPro.TextMeshProUGUI, Unity.TextMeshPro");
                    if (tmpType == null)
                        tmpType = Type.GetType("TMPro.TextMeshProUGUI, Unity.TextMeshPro, Version=0.0.0.0, Culture=neutral, PublicKeyToken=null");
                    // Fallback: search loaded assemblies
                    if (tmpType == null)
                    {
                        foreach (Assembly a in AppDomain.CurrentDomain.GetAssemblies())
                            if (a.GetName().Name == "Unity.TextMeshPro")
                            { tmpType = a.GetType("TMPro.TextMeshProUGUI"); break; }
                    }
                    UnityEngine.Debug.Log("[W40KRTAudioDirectMod] TMPro type found: " + (tmpType != null) + " fullname=" + (tmpType != null ? tmpType.FullName : "null"));
                    if (tmpType != null)
                    {
                        // Patch BASE class TMP_Text.set_text (set_text is virtual, defined on TMP_Text)
                        Type baseType = tmpType.BaseType;
                        if (baseType != null && baseType.FullName == "TMPro.TMP_Text")
                        {
                            var setText = baseType.GetMethod("set_text", new Type[] { typeof(string) });
                            if (setText != null)
                            {
                                var h = new Harmony("W40KRTAudioDirectMod.TMP");
                                h.Patch(setText, prefix: new HarmonyMethod(typeof(Main), "OnTextSet"));
                                UnityEngine.Debug.Log("[W40KRTAudioDirectMod] TMP_Text.set_text patched!");
                            }
                        }
                        // Also patch legacy Text component if available
                        Type legacyText = Type.GetType("UnityEngine.UI.Text, UnityEngine.UI");
                        if (legacyText == null)
                        {
                            foreach (Assembly a in AppDomain.CurrentDomain.GetAssemblies())
                                if (a.GetName().Name == "UnityEngine.UI")
                                { legacyText = a.GetType("UnityEngine.UI.Text"); break; }
                        }
                        if (legacyText != null)
                        {
                            var setLegacy = legacyText.GetMethod("set_text", new Type[] { typeof(string) });
                            if (setLegacy != null)
                            {
                                var h2 = new Harmony("W40KRTAudioDirectMod.Legacy");
                                h2.Patch(setLegacy, prefix: new HarmonyMethod(typeof(Main), "OnTextSet"));
                                UnityEngine.Debug.Log("[W40KRTAudioDirectMod] Legacy Text.set_text patched!");
                            }
                        }
                    }
                }
                catch (Exception ex) { UnityEngine.Debug.Log("[W40KRTAudioDirectMod] Patch err: " + ex.Message); }
            }
        }

        public static void OnTextSet(string value)
        {
            if (!Main.Enabled) return;
            if (value != null && value.Length > 3)
            {
                string trunc = value.Substring(0, Math.Min(120, value.Length));
                // Log interesting texts only (skip "100%" spam)
                if (value != "100%" && !value.StartsWith("20/") && !value.StartsWith("Shift+") && !value.StartsWith("Ctrl+"))
                    UnityEngine.Debug.Log("[W40KRTAudioDirectMod] Text: " + trunc);
                if (!played36 && (value.IndexOf("Да будет известно") >= 0 || value.IndexOf("Патента Вольного Торговца") >= 0))
                {
                    played36 = true;
                    string path;
                    if (guidToWav.TryGetValue("36a60f39-1962-464e-8bdc-ea78e5559370", out path))
                        PlaySound(path, IntPtr.Zero, SND_FILENAME | SND_ASYNC);
                }
                if (value.IndexOf("ослепительным примером") >= 0)
                {
                    string path;
                    if (guidToWav.TryGetValue("7d7fdde5-2ea2-4194-b0c5-b1b672268fbc", out path))
                        PlaySound(path, IntPtr.Zero, SND_FILENAME | SND_ASYNC);
                }
                if (value.IndexOf("возвыситься над") >= 0)
                {
                    string path;
                    if (guidToWav.TryGetValue("9e22eda7-5e0c-4bd0-aff6-5e535872b847", out path))
                        PlaySound(path, IntPtr.Zero, SND_FILENAME | SND_ASYNC);
                }
            }
        }

        public static void PlayClip(string guid)
        {
            if (!Enabled) return;
            string path;
            if (guidToWav.TryGetValue(guid, out path))
                PlaySound(path, IntPtr.Zero, SND_FILENAME | SND_ASYNC);
        }
    }

    [HarmonyPatch("Kingmaker.Code.UI.MVVM.VM.Dialog.Dialog.DialogVM", "HandleOnCueShow")]
    public static class DialogCuePatch
    {
        private static bool tried;

        [HarmonyPostfix]
        public static void Postfix()
        {
            if (!Main.Enabled) return;

            // On first call, try to log all available types to find Game.Instance
            if (!tried)
            {
                tried = true;
                try
                {
                    Type gt = null;
                    foreach (Type t in AccessTools.AllTypes())
                        if (t.FullName == "Kingmaker.Game") { gt = t; break; }
                    UnityEngine.Debug.Log("[W40KRTAudioDirectMod] Game type: " + (gt != null));
                    if (gt != null)
                    {
                        var p = gt.GetProperty("Instance", BindingFlags.Public | BindingFlags.Static);
                        UnityEngine.Debug.Log("[W40KRTAudioDirectMod] Instance prop: " + (p != null));
                        if (p != null)
                        {
                            var gi = p.GetValue(null, null);
                            UnityEngine.Debug.Log("[W40KRTAudioDirectMod] Game.Instance: " + (gi != null));
                            if (gi != null)
                            {
                                var dc = findDialogController(gi);
                                UnityEngine.Debug.Log("[W40KRTAudioDirectMod] DialogController: " + (dc != null));
                                if (dc != null)
                                {
                                    var cueP = dc.GetType().GetProperty("CurrentCue");
                                    if (cueP != null)
                                    {
                                        var cue = cueP.GetValue(dc, null);
                                        UnityEngine.Debug.Log("[W40KRTAudioDirectMod] CurrentCue: " + (cue != null));
                                        if (cue != null)
                                        {
                                            var textP = cue.GetType().GetProperty("LocalizedStringText");
                                            if (textP == null) textP = cue.GetType().GetProperty("DisplayText");
                                            UnityEngine.Debug.Log("[W40KRTAudioDirectMod] Text prop: " + (textP != null));
                                            if (textP != null)
                                            {
                                                var txt = textP.GetValue(cue, null);
                                                if (txt != null)
                                                {
                                                    var keyP = txt.GetType().GetProperty("Key");
                                                    if (keyP != null)
                                                    {
                                                        var key = (string)keyP.GetValue(txt, null);
                                                        UnityEngine.Debug.Log("[W40KRTAudioDirectMod] Key=" + key);
                                                        Main.PlayClip(key);
                                                    }
                                                }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }
                catch (Exception ex) { UnityEngine.Debug.Log("[W40KRTAudioDirectMod] Init err: " + ex.Message); }
            }
        }

        private static object findDialogController(object gi)
        {
            foreach (var p in gi.GetType().GetProperties())
                if (p.Name.ToLower().Contains("dialog")) return p.GetValue(gi, null);
            foreach (var f in gi.GetType().GetFields(BindingFlags.Instance | BindingFlags.Public | BindingFlags.NonPublic))
                if (f.Name.ToLower().Contains("dialog")) return f.GetValue(gi);
            return null;
        }
    }
}
