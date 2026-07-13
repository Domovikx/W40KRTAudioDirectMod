param(
    [Parameter(Mandatory=$true)]
    [string]$Text,
    [Parameter(Mandatory=$true)]
    [string]$Output,
    [string]$Voice = "Microsoft Dmitry Online",
    [int]$Rate = 0,
    [float]$TargetDuration = 0
)

Add-Type -AssemblyName System.Speech

function Get-WavDuration($path) {
    $bytes = [System.IO.File]::ReadAllBytes($path)
    if ($bytes.Length -lt 44) { return 0 }
    $sampleRate = [BitConverter]::ToUInt32($bytes, 24)
    $channels = [BitConverter]::ToUInt16($bytes, 22)
    $bitsPerSample = [BitConverter]::ToUInt16($bytes, 34)
    $pos = 12
    $dataSize = 0
    while ($pos -lt $bytes.Length - 8) {
        $chunkId = [System.Text.Encoding]::ASCII.GetString($bytes[$pos..($pos+3)])
        $chunkSize = [BitConverter]::ToUInt32($bytes, $pos+4)
        if ($chunkId -eq "data") { $dataSize = $chunkSize; break }
        $pos += 8 + $chunkSize
        if ($chunkSize -eq 0) { break }
    }
    if ($dataSize -eq 0) { return 0 }
    $bytesPerSample = $bitsPerSample / 8
    $samples = $dataSize / $bytesPerSample
    return $samples / ($sampleRate * $channels)
}

function Generate($rate) {
    $synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
    try { $synth.SelectVoice($Voice) } catch { Write-Warning "Voice not found, using default" }
    $synth.Rate = $rate
    $synth.SetOutputToWaveFile($Output)
    $synth.Speak($Text)
    $synth.Dispose()
}

if ($TargetDuration -gt 0) {
    # Generate at Rate 0 to get baseline
    Write-Host "Measuring baseline (Rate=0)..."
    Generate(0)
    $baseDur = Get-WavDuration($Output)
    Write-Host "  Baseline: $('{0:F1}' -f $baseDur)s at Rate=0"

    if ($baseDur -gt $TargetDuration) {
        $factor = $baseDur / $TargetDuration
        # Estimate Rate needed: Rate 0 = 10.6s -> 7.6s at Rate 2 -> 5.9s at Rate 4
        # This is roughly: Rate = ($baseDur / $TargetDuration - 1) * ~3.5
        $estRate = [Math]::Round(($baseDur / $TargetDuration - 1) * 3.5)
        $estRate = [Math]::Max(-5, [Math]::Min(10, $estRate))
        Write-Host "  Estimated Rate=$estRate (target $('{0:F1}' -f $TargetDuration)s, factor $('{0:F2}' -f $factor))"

        Generate($estRate)
        $newDur = Get-WavDuration($Output)
        Write-Host "  Result: $('{0:F1}' -f $newDur)s at Rate=$estRate"

        # If still too long, try one more iteration
        if ($newDur -gt $TargetDuration * 1.1 -and $estRate -lt 10) {
            $adjRate = $estRate + 1
            Generate($adjRate)
            $newDur = Get-WavDuration($Output)
            Write-Host "  Adjusted to Rate=$adjRate: $('{0:F1}' -f $newDur)s"
        }
    } else {
        Write-Host "  Already fits, keeping Rate=0"
    }
} else {
    Generate($Rate)
}

Write-Host "Done: $Output ($('{0:F1}' -f (Get-WavDuration($Output)))s)"
