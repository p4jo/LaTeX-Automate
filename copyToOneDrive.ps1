param(
    [Alias( "f", "only", "p")]
    [string] $folder = ""
)
$ODP = "/Dok/LaTeX-output"
$pathOK = 0
Write-Host "This is copyToOneDrive. Make sure you have set `$Path_OneDrive in your `$profile. Else we use YourPersonalOneDrive/$ODP"

if ($f -ne ""){
    $p = (Get-Variable 'Path_OneDrive' -ErrorAction 'Ignore' -ValueOnly); 
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

# Set this by editing $profile.AllUsersAllHosts or similar