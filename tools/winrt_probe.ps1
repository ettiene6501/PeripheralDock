param(
    [string]$Address = "4873CB476268",
    [switch]$Scan
)

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$OutputEncoding = [Console]::OutputEncoding
Add-Type -AssemblyName System.Runtime.WindowsRuntime

$asTaskGeneric = ([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object {
    $_.Name -eq "AsTask" -and
    $_.GetParameters().Count -eq 1 -and
    $_.GetParameters()[0].ParameterType.Name -eq "IAsyncOperation``1"
})[0]

function Await($WinRtTask, $ResultType) {
    $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
    $netTask = $asTask.Invoke($null, @($WinRtTask))
    $netTask.Wait(-1) | Out-Null
    $netTask.Result
}

function AwaitAction($WinRtAction) {
    $netTask = [System.WindowsRuntimeSystemExtensions]::AsTask($WinRtAction)
    $netTask.Wait(-1) | Out-Null
}

$out = [ordered]@{
    address = $Address
    classic_device_found = $false
    classic_name = $null
    classic_connection_status = $null
    device_found = $false
    device_name = $null
    connection_status = $null
    gatt_status = $null
    gatt_services = @()
    battery_service_found = $false
    battery_level = $null
    error = $null
}

try {
    $addr = [Convert]::ToUInt64($Address, 16)
    $null = [Windows.Devices.Bluetooth.BluetoothDevice, Windows.Devices.Bluetooth, ContentType = WindowsRuntime]
    $classicOp = [Windows.Devices.Bluetooth.BluetoothDevice]::FromBluetoothAddressAsync($addr)
    $classic = Await $classicOp ([Windows.Devices.Bluetooth.BluetoothDevice])
    if ($null -ne $classic) {
        $out.classic_device_found = $true
        $out.classic_name = $classic.Name
        $out.classic_connection_status = "$($classic.ConnectionStatus)"
    }
}
catch {
    $out.classic_error = "$($_.Exception.GetType().Name): $($_.Exception.Message)"
}

try {
    $addr = [Convert]::ToUInt64($Address, 16)
    $null = [Windows.Devices.Bluetooth.BluetoothLEDevice, Windows.Devices.Bluetooth, ContentType = WindowsRuntime]
    $null = [Windows.Devices.Bluetooth.GenericAttributeProfile.GattDeviceService, Windows.Devices.Bluetooth, ContentType = WindowsRuntime]
    $null = [Windows.Devices.Bluetooth.GenericAttributeProfile.GattCharacteristic, Windows.Devices.Bluetooth, ContentType = WindowsRuntime]

    $op = [Windows.Devices.Bluetooth.BluetoothLEDevice]::FromBluetoothAddressAsync($addr)
    $dev = Await $op ([Windows.Devices.Bluetooth.BluetoothLEDevice])
    if ($null -eq $dev) {
        $out.error = "FromBluetoothAddressAsync returned null (no BLE object)"
    }
    else {
        $out.device_found = $true
        $out.device_name = $dev.Name
        $out.connection_status = "$($dev.ConnectionStatus)"
        $out.device_id = $dev.DeviceId

        $uuid = [Guid]"0000180f-0000-1000-8000-00805f9b34fb"
        $svcOp = $dev.GetGattServicesForUuidAsync($uuid, [Windows.Devices.Bluetooth.BluetoothCacheMode]::Uncached)
        $svcResult = Await $svcOp ([Windows.Devices.Bluetooth.GenericAttributeProfile.GattDeviceServicesResult])
        $out.gatt_status = "$($svcResult.Status)"
        foreach ($svc in $svcResult.Services) {
            $out.battery_service_found = $true
            $out.gatt_services += $svc.Uuid.ToString()
            $charOp = $svc.GetCharacteristicsForUuidAsync(
                [Guid]"00002a19-0000-1000-8000-00805f9b34fb",
                [Windows.Devices.Bluetooth.BluetoothCacheMode]::Uncached
            )
            $charResult = Await $charOp ([Windows.Devices.Bluetooth.GenericAttributeProfile.GattCharacteristicsResult])
            foreach ($ch in $charResult.Characteristics) {
                $readOp = $ch.ReadValueAsync([Windows.Devices.Bluetooth.BluetoothCacheMode]::Uncached)
                $readResult = Await $readOp ([Windows.Devices.Bluetooth.GenericAttributeProfile.GattReadResult])
                if ($readResult.Status -eq "Success") {
                    $reader = [Windows.Storage.Streams.DataReader]::FromBuffer($readResult.Value)
                    $value = $reader.ReadByte()
                    $out.battery_level = $value
                }
                else {
                    $out.error = "Battery Level 讀取失敗: $($readResult.Status)"
                }
            }
        }
    }
}
catch {
    $out.error = "$($_.Exception.GetType().Name): $($_.Exception.Message)"
}

if ($Scan) {
    try {
        $null = [Windows.Devices.Bluetooth.BluetoothLEDevice, Windows.Devices.Bluetooth, ContentType = WindowsRuntime]
        $selector = [Windows.Devices.Bluetooth.BluetoothLEDevice]::GetDeviceSelector()
        $null = [Windows.Devices.Enumeration.DeviceInformation, Windows.Devices.Enumeration, ContentType = WindowsRuntime]
        $findOp = [Windows.Devices.Enumeration.DeviceInformation]::FindAllAsync($selector)
        $infos = Await $findOp ([Windows.Devices.Enumeration.DeviceInformationCollection])
        $out.le_devices = @($infos | ForEach-Object { [ordered]@{ Name = $_.Name; Id = $_.Id } })
    }
    catch {
        $out.scan_error = "$($_.Exception.GetType().Name): $($_.Exception.Message)"
    }
}

$out | ConvertTo-Json -Depth 5
