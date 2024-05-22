param(
    [Alias( "f", "only", "p")]
    [string] $folder = "",
    [Alias ("onedrivePath", "subpath")]
    [string] $ODP = "/Dok/LaTeX-output"
)
Write-Host "This is copyToOneDrive. Make sure you have set `$Path_OneDrive in your `$profile. Else we use YourPersonalOneDrive$ODP"

if ($f -ne ""){
    $pathOK = 0
    $p = (Get-Variable 'Path_OneDrive' -ErrorAction 'Ignore' -ValueOnly); 
    # Set this by editing $profile.AllUsersAllHosts or similar
    if ($p -and (Test-Path $p)) { 
        Write-Host "Copying to `$Path_OneDrive = $p"
        $pathOK = 1
    } else {
        $p = $env:OneDriveConsumer + $ODP
        if ($p -and (Test-Path $p)) { 
            Write-Host "Copying to `$env:OneDriveConsumer + `$onedrivePath = $p"
            $pathOK = 1
        }
    } if ($pathOK) {
        Copy-Item -Path "$folder/*.pdf" -Destination "$p" -Verbose
    } else {
        Write-Host "Path not set or not found: $p"
    }
} else {
    Write-Host "No folder provided"
}
