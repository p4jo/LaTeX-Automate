param(
    [Alias( "f", "only", "p")]
    [string] $folder = ""
)

if ($f -ne ""){
    $p = (Get-Variable 'Path_OneDrive' -ErrorAction 'Ignore'); 
    if ($p -and (Test-Path $p)) { 
        Copy-Item -Path "$folder/*.pdf" -Destination "$p/Dok/LaTeX-output"
    }
}

# Set this by editing $profile.AllUsersAllHosts or similar