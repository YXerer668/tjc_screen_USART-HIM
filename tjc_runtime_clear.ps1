param(
    [string]$PortName = 'COM36',
    [int]$BaudRate = 9600
)

$ErrorActionPreference = 'Stop'

function Send-TjcCommand {
    param(
        [System.IO.Ports.SerialPort]$SerialPort,
        [string]$Command
    )

    $payload = [byte[]]([System.Text.Encoding]::ASCII.GetBytes($Command) + 0xFF + 0xFF + 0xFF)
    $SerialPort.Write($payload, 0, $payload.Length)
    Start-Sleep -Milliseconds 30
}

$serialPort = New-Object System.IO.Ports.SerialPort $PortName, $BaudRate, 'None', 8, 'One'
$serialPort.ReadTimeout = 250
$serialPort.WriteTimeout = 250
$serialPort.Handshake = 'None'

try {
    $serialPort.Open()
    Start-Sleep -Milliseconds 120
    Send-TjcCommand -SerialPort $serialPort -Command 'page 0'
    Send-TjcCommand -SerialPort $serialPort -Command 'ref_stop'
    Send-TjcCommand -SerialPort $serialPort -Command 'fill 0,0,800,480,65535'
    Send-TjcCommand -SerialPort $serialPort -Command 'ref_star'
}
finally {
    if ($serialPort.IsOpen) {
        $serialPort.Close()
    }
    $serialPort.Dispose()
}
