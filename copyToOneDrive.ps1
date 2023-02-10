param(
    [Alias( "f", "only", "p")]
    [string] $folder = ""
)

Write-Host "This is copyToOneDrive. Make sure you have set `$Path_OneDrive in your `$profile"
if ($f -ne ""){
    $p = (Get-Variable 'Path_OneDrive' -ErrorAction 'Ignore' -ValueOnly); 
    if ($p -and (Test-Path $p)) { 
        Write-Host "Copying to `$Path_OneDrive = $p "
        Copy-Item -Path "$folder/*.pdf" -Destination "$p/Dok/LaTeX-output" -Verbose
    } else {
        Write-Host "Path not set or not found: $p"
    }
} else {
    Write-Host "No folder provided"
}

# Set this by editing $profile.AllUsersAllHosts or similar