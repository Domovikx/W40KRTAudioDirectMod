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

            var harmony = new Harmony(modEntry.Info.Id);
            harmony.PatchAll(Assembly.GetExecutingAssembly());

            // Manually patch BarkPlayer.Bark
            try
            {
                foreach (Assembly asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    if (asm.GetName().Name == "Code")
                    {
                        Type bp = asm.GetType("Kingmaker.Code.UI.MVVM.VM.Bark.BarkPlayer");
                        if (bp != null)
                        {
                            foreach (MethodInfo m in bp.GetMethods())
                            {
                                if (m.Name == "Bark")
                                {
                                    ParameterInfo[] pars = m.GetParameters();
                                    if (pars.Length >= 2 && pars[1].ParameterType == typeof(string))
                                    {
                                        harmony.Patch(m, prefix: new HarmonyMethod(typeof(Main), "OnBark"));
                                        break;
                                    }
                                }
                            }
                        }
                        break;
                    }
                }
            }
            catch { }

            modEntry.OnToggle = (entry, value) => { Enabled = value; return true; };
            modEntry.OnUpdate = OnUpdate;

            return true;
        }

        static bool delayedPatched;

        static int updateCount;

        static void OnUpdate(UnityModManager.ModEntry modEntry, float delta)
        {
            updateCount++;
            if (updateCount == 1)
                UnityEngine.Debug.Log("[W40KRTAudioDirectMod] OnUpdate called");
            if (delayedPatched) return;
            try
            {
                foreach (Assembly asm in AppDomain.CurrentDomain.GetAssemblies())
                {
                    if (asm.GetName().Name == "Unity.TextMeshPro")
                    {
                        Type t = asm.GetType("TMPro.TextMeshProUGUI");
                        if (t != null)
                        {
                            var m = t.GetMethod("set_text", new Type[] { typeof(string) });
                            if (m != null)
                            {
                                new Harmony("W40KRTAudioDirectMod.TMP").Patch(m, prefix: new HarmonyMethod(typeof(Main), "OnText"));
                            }
                        }
                        delayedPatched = true;
                        break;
                    }
                }
            }
            catch { delayedPatched = true; }
        }

        public static void OnText(string value)
        {
            if (!Enabled || played36) return;
            if (value != null && value.IndexOf("Let it be known") >= 0)
            {
                played36 = true;
                string path;
                if (guidToWav.TryGetValue("36a60f39-1962-464e-8bdc-ea78e5559370", out path))
                    PlaySound(path, IntPtr.Zero, SND_FILENAME | SND_ASYNC);
            }
        }

        public static void OnBark(string text)
        {
            if (!Enabled || played36) return;
            if (text != null && text.IndexOf("Let it be known") >= 0)
            {
                played36 = true;
                string path;
                if (guidToWav.TryGetValue("36a60f39-1962-464e-8bdc-ea78e5559370", out path))
                    PlaySound(path, IntPtr.Zero, SND_FILENAME | SND_ASYNC);
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
        private static PropertyInfo instanceP, cueP, textP, keyP, dispP;

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

                if (cueP == null) cueP = dc.GetType().GetProperty("CurrentCue");
                if (cueP == null) return;
                object cue = cueP.GetValue(dc, null);
                if (cue == null) return;

                if (textP == null) textP = cue.GetType().GetProperty("LocalizedStringText");
                if (textP == null) textP = cue.GetType().GetProperty("DisplayText");
                if (textP == null) return;
                object txt = textP.GetValue(cue, null);
                if (txt == null) return;

                if (keyP == null) keyP = txt.GetType().GetProperty("Key");
                string k = keyP != null ? (string)keyP.GetValue(txt, null) : null;
                if (!string.IsNullOrEmpty(k)) Main.PlayClip(k);

                if (dispP == null) dispP = cue.GetType().GetProperty("DisplayText");
                if (dispP != null)
                {
                    object dt = dispP.GetValue(cue, null);
                    if (dt != null && dt is string && ((string)dt).IndexOf("Let it be known") >= 0)
                        Main.PlayClip("36a60f39-1962-464e-8bdc-ea78e5559370");
                }
            }
            catch { }
        }
    }
}
