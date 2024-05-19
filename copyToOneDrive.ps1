param(
    [Alias( "f", "only", "p")]
    [string] $folder = "",
    [Alias ("onedrivePath", "subpath")]
    [string] $ODP = "/Dok/LaTeX-output"
)
Write-Host "This is copyToOneDrive. Make sure you have set `$Path_OneDrive in your `$profile. Else we use YourPersonalOneDrive/$ODP"

if ($f -ne ""){
    $pathOK = 0
    $p = (Get-Variable 'Path_OneDrive' -ErrorAction 'Ignore' -ValueOnly); 
    # Set this by editing $profile.AllUsersAllHosts or similar
    if ($p -and (Test-Path $p)) { 
        Write-Host "Copying to `$Path_OneDrive = $p"
        $pathOK = 1
    } else {
        $p = (Get-Variable $env:OneDriveConsumer -ErrorAction Ignore -ValueOnly) -join $ODP
        if ($p -and (Test-Path $p)) { 
            Write-Host "Copying to `$env:OneDriveConsumer = $p, subpath $ODP"
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
