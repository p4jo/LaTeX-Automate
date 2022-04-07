param(
    [Alias("f","o","project","p")]
    [string] $folder = ""
)
$folder = $folder.TrimEnd(".tex").TrimEnd('/').TrimEnd('\')
$logfile            = -join($folder,".log")
$destination  = -join($folder, "\.log")
if ((Test-Path $logfile) -and (Test-Path $folder)) {
    Copy-Item $logfile -Destination $destination
}
