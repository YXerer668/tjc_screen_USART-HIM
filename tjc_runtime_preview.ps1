param(
    [string]$PortName = 'COM36',
    [int]$BaudRate = 9600
)

$ErrorActionPreference = 'Stop'

function Convert-Rgb565Value {
    param(
        [int]$R,
        [int]$G,
        [int]$B
    )

    return (($R -band 0xF8) -shl 8) -bor (($G -band 0xFC) -shl 3) -bor ($B -shr 3)
}

function Send-TjcCommand {
    param(
        [System.IO.Ports.SerialPort]$SerialPort,
        [string]$Command
    )

    $payload = [byte[]]([System.Text.Encoding]::ASCII.GetBytes($Command) + 0xFF + 0xFF + 0xFF)
    $SerialPort.Write($payload, 0, $payload.Length)
    Start-Sleep -Milliseconds 35
}

function Draw-String {
    param(
        [System.IO.Ports.SerialPort]$SerialPort,
        [int]$X,
        [int]$Y,
        [int]$W,
        [int]$H,
        [int]$FontId,
        [int]$FontColor,
        [int]$BackColor,
        [int]$XCenter,
        [int]$YCenter,
        [int]$Sta,
        [string]$Text
    )

    $safeText = $Text.Replace('"', '\"')
    $cmd = "xstr $X,$Y,$W,$H,$FontId,$FontColor,$BackColor,$XCenter,$YCenter,$Sta,""$safeText"""
    Send-TjcCommand -SerialPort $SerialPort -Command $cmd
}

$bg = Convert-Rgb565Value 245 244 239
$panel = Convert-Rgb565Value 255 255 255
$nav = Convert-Rgb565Value 34 40 49
$navAccent = Convert-Rgb565Value 255 184 76
$title = Convert-Rgb565Value 45 52 64
$body = Convert-Rgb565Value 97 108 125
$mint = Convert-Rgb565Value 82 196 182
$blue = Convert-Rgb565Value 79 116 255
$peach = Convert-Rgb565Value 255 141 112
$line = Convert-Rgb565Value 222 226 230
$shadow = Convert-Rgb565Value 228 230 234

$serialPort = New-Object System.IO.Ports.SerialPort $PortName, $BaudRate, 'None', 8, 'One'
$serialPort.ReadTimeout = 250
$serialPort.WriteTimeout = 250
$serialPort.Handshake = 'None'
$serialPort.DtrEnable = $false
$serialPort.RtsEnable = $false

try {
    $serialPort.Open()
    Start-Sleep -Milliseconds 150

    Send-TjcCommand -SerialPort $serialPort -Command 'page 0'
    Send-TjcCommand -SerialPort $serialPort -Command 'ref_stop'

    Send-TjcCommand -SerialPort $serialPort -Command "fill 0,0,800,480,$bg"
    Send-TjcCommand -SerialPort $serialPort -Command "fill 24,22,752,64,$nav"
    Send-TjcCommand -SerialPort $serialPort -Command "fill 24,106,236,160,$shadow"
    Send-TjcCommand -SerialPort $serialPort -Command "fill 20,102,236,160,$panel"
    Send-TjcCommand -SerialPort $serialPort -Command "fill 284,106,236,160,$shadow"
    Send-TjcCommand -SerialPort $serialPort -Command "fill 280,102,236,160,$panel"
    Send-TjcCommand -SerialPort $serialPort -Command "fill 548,106,232,160,$shadow"
    Send-TjcCommand -SerialPort $serialPort -Command "fill 544,102,232,160,$panel"
    Send-TjcCommand -SerialPort $serialPort -Command "fill 20,294,760,150,$shadow"
    Send-TjcCommand -SerialPort $serialPort -Command "fill 20,290,760,150,$panel"

    Send-TjcCommand -SerialPort $serialPort -Command "fill 44,332,152,74,$mint"
    Send-TjcCommand -SerialPort $serialPort -Command "fill 232,332,152,74,$blue"
    Send-TjcCommand -SerialPort $serialPort -Command "fill 420,332,152,74,$peach"
    Send-TjcCommand -SerialPort $serialPort -Command "fill 608,332,152,74,$nav"

    Send-TjcCommand -SerialPort $serialPort -Command "fill 44,70,88,4,$navAccent"
    Send-TjcCommand -SerialPort $serialPort -Command "draw 20,287,779,287,$line"

    Draw-String -SerialPort $serialPort -X 44 -Y 32 -W 300 -H 32 -FontId 0 -FontColor 65535 -BackColor $nav -XCenter 0 -YCenter 1 -Sta 1 -Text 'TJC UI Preview'
    Draw-String -SerialPort $serialPort -X 44 -Y 58 -W 420 -H 22 -FontId 0 -FontColor (Convert-Rgb565Value 210 216 226) -BackColor $nav -XCenter 0 -YCenter 1 -Sta 1 -Text 'warm light theme / cleaner hierarchy'

    Draw-String -SerialPort $serialPort -X 42 -Y 126 -W 180 -H 26 -FontId 0 -FontColor $body -BackColor $panel -XCenter 0 -YCenter 1 -Sta 1 -Text 'MAIN STATUS'
    Draw-String -SerialPort $serialPort -X 42 -Y 160 -W 180 -H 42 -FontId 0 -FontColor $title -BackColor $panel -XCenter 0 -YCenter 1 -Sta 1 -Text 'Ready'
    Draw-String -SerialPort $serialPort -X 42 -Y 206 -W 180 -H 24 -FontId 0 -FontColor $body -BackColor $panel -XCenter 0 -YCenter 1 -Sta 1 -Text 'soft card + bold title'

    Draw-String -SerialPort $serialPort -X 302 -Y 126 -W 180 -H 26 -FontId 0 -FontColor $body -BackColor $panel -XCenter 0 -YCenter 1 -Sta 1 -Text 'AUDIO CHAIN'
    Draw-String -SerialPort $serialPort -X 302 -Y 160 -W 180 -H 42 -FontId 0 -FontColor $title -BackColor $panel -XCenter 0 -YCenter 1 -Sta 1 -Text 'UART > DSP'
    Draw-String -SerialPort $serialPort -X 302 -Y 206 -W 180 -H 24 -FontId 0 -FontColor $body -BackColor $panel -XCenter 0 -YCenter 1 -Sta 1 -Text 'less white / more focus'

    Draw-String -SerialPort $serialPort -X 566 -Y 126 -W 180 -H 26 -FontId 0 -FontColor $body -BackColor $panel -XCenter 0 -YCenter 1 -Sta 1 -Text 'LOOK & FEEL'
    Draw-String -SerialPort $serialPort -X 566 -Y 160 -W 180 -H 42 -FontId 0 -FontColor $title -BackColor $panel -XCenter 0 -YCenter 1 -Sta 1 -Text 'Calm + Clear'
    Draw-String -SerialPort $serialPort -X 566 -Y 206 -W 180 -H 24 -FontId 0 -FontColor $body -BackColor $panel -XCenter 0 -YCenter 1 -Sta 1 -Text '3-color action rhythm'

    Draw-String -SerialPort $serialPort -X 40 -Y 308 -W 220 -H 26 -FontId 0 -FontColor $body -BackColor $panel -XCenter 0 -YCenter 1 -Sta 1 -Text 'Suggested button style'

    Draw-String -SerialPort $serialPort -X 44 -Y 352 -W 152 -H 34 -FontId 0 -FontColor 65535 -BackColor $mint -XCenter 1 -YCenter 1 -Sta 1 -Text 'Play'
    Draw-String -SerialPort $serialPort -X 232 -Y 352 -W 152 -H 34 -FontId 0 -FontColor 65535 -BackColor $blue -XCenter 1 -YCenter 1 -Sta 1 -Text 'Settings'
    Draw-String -SerialPort $serialPort -X 420 -Y 352 -W 152 -H 34 -FontId 0 -FontColor 65535 -BackColor $peach -XCenter 1 -YCenter 1 -Sta 1 -Text 'Record'
    Draw-String -SerialPort $serialPort -X 608 -Y 352 -W 152 -H 34 -FontId 0 -FontColor 65535 -BackColor $nav -XCenter 1 -YCenter 1 -Sta 1 -Text 'System'

    Draw-String -SerialPort $serialPort -X 40 -Y 420 -W 620 -H 18 -FontId 0 -FontColor $body -BackColor $panel -XCenter 0 -YCenter 1 -Sta 1 -Text 'This is a temporary live preview drawn over page0.'

    Send-TjcCommand -SerialPort $serialPort -Command 'ref_star'
}
finally {
    if ($serialPort.IsOpen) {
        $serialPort.Close()
    }
    $serialPort.Dispose()
}
