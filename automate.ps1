param(
    [Alias("b", "r", "root")]
    [string] $BaseDirectory = "",

    [Alias( "f", "folder", "only", "p")]
    [string] $project = "",

    [Alias("all")]
    [switch] $AllIfFolderDoesntExist = $false, # Im Zweifel alle

    [Alias("o", "overwrite", "renew")]
    [switch] $RenewMainFile = $false,

    [Alias("a")]
    [string] $author = "Johannes Heißler",
    
    [Alias("l", "log", "backupLog", "s")]
    [switch] $saveLog = $false,

    [Alias("h", "help")]
    [switch] $getHelp = $false
)

Write-Host "This is JHAutomate." -ForegroundColor Green

if ($getHelp) {
    Write-Host "This script auto generates a file with an \input statement for every .tex file in the folder specified with -p"
    Get-Help .\automate.ps1
    exit
}

function getIncludedTexFiles{
    param(
        $path,
        [switch] $log = $false
    )
    $name = (Split-Path $path -Leaf)
    $allProjectFiles = (Get-ChildItem -Path $path -Filter *.tex -Exclude *_generated.tex, *$name.tex, _*, *_ -Recurse)
    $includedProjectFiles = $allProjectFiles | Where-Object {-not (Test-Path (-join($_.Directory.FullName, "\.texignore")))} 
    
    if($log) {
        $excludedProjectFiles = $allProjectFiles | Where-Object {$includedProjectFiles -notcontains $_}

        $excludedProjectFiles | ForEach-Object {
                Write-Host "`tSkipped`t" -ForegroundColor Red -NoNewline
                Write-Host "`"$_`"." -ForegroundColor Gray
            }

        $includedProjectFiles | ForEach-Object {
                Write-Host "`tAdded`t" -ForegroundColor Green -NoNewline
                Write-Host "`"$_`"." -ForegroundColor Gray
            }
    }

    return $includedProjectFiles
}

function generatedContent ($path, $rootPath) {
    
    $currentPath = $path.FullName.Replace("\","/")
    $texstring = ""     
    
    (getIncludedTexFiles -path $path -log $true) | #Alle tex-Dateien in allen Unterordnern anschauen, ausschließen mit _.
    ForEach-Object { # foreach(tex-Datei $path in $path)
        $PfadAufgelisteteInhaltsTex =  $_.FullName.Replace("\","/") #Resolve-Path#-Relative
        $texstring = "$texstring\input{$PfadAufgelisteteInhaltsTex}`n"
    }
    
    if ($texstring -eq "") { return "" }

    return "% !TEX root = $rootPath 
\def\currentPath{$currentPath}
$texstring
% Automatisch generierte Datei, jede Änderung wird wieder überschrieben"

}

function GetPathMainFile ($name, $reverseRelative) {
    $legacyPathMainFile = "./$name.tex"
    if (-not $reverseRelative){
        if(Test-Path $legacyPathMainFile){
            return $legacyPathMainFile
        }
        return "./$name/$name.tex"
    }
    if(Test-Path $legacyPathMainFile){
        return "../$name.tex"
    }
    return "$name.tex"
}
function GetPathGeneratedFile ($name, $relative = $false) {
    $legacyPathMainFile = "./$name.tex"
    if (-not $relative){
        return -join("./$name/$name", "_generated.tex")
    }
    if(Test-Path $legacyPathMainFile){
        return -join("$name/$name", "_generated.tex")
    }
    return -join("$name", "_generated.tex") 
}

## OLD MAIN FILE STYLE
# - project.tex
# - project
#    · project_generated.tex
#    · stuff.tex
# - project.pdf
# - project.log and all the other generated files

## NEW MAIN FILE SYSTEM
# - project
#    · project.tex
#    · project_generated.tex
#    · stuff.tex
#    · out  
#       - project.pdf
#       - project.log and all the other generated files


function MakeNewRootFile($name, $contentFilePath) {
   $pathMainFile = GetPathMainFile -name $name

    Write-Host "Will write a new main file for $name. The old one will be backed up." -ForegroundColor Yellow

    $mainFileExists = (Test-Path $pathMainFile)
    $backupFileExists = (Test-Path $pathMainFile.bak)
    if($mainFileExists -and $backupFileExists){
        Remove-Item $pathMainFile.bak
    }
    if($mainFileExists){
        Rename-Item $pathMainFile $pathMainFile.bak
    }
    
"\newcommand\TITLE{$name}
\newcommand\AUTHOR{$author}
\documentclass[
    title=\TITLE,
    author=\AUTHOR,
    STIX,
    simpleTitle,
    omitFloat
]
{JHPreamble} 

% \RequirePackage{icomma} % macht Kommas ohne Leerzeichen danach zu Kommas ohne Abstand danach

\hypersetup{
    pdfsubject  = {$name},
    pdfkeywords = {$name}
}

% \addbibresource{./$name/Referenzen.bib}

\begin{document}

\Inhaltsverzeichnis

\input{$contentFilePath}

\end{document}" | Out-File -FilePath $pathMainFile -Encoding utf8 
           
}

# FIX INPUTS AND PATHS

if ($BaseDirectory -ne ""){
    Set-Location $BaseDirectory
}
else{
    $BaseDirectory = Get-Location
}

Write-Host "Base directory = ""$BaseDirectory"", Author for new main files: ""$author""."

if ($project.EndsWith(".tex") -or (Test-Path "$project.tex")){
    $project = $project.TrimEnd(".tex")
    $projectBasePath = (Split-Path $project)
    if ( $projectBasePath -eq $BaseDirectory){
        $project = (Split-Path -Leaf -Path $project)
    }
    else{
        $project = $projectBasePath
    }
}
else{
    if ($project -ne ""){
        $project = (Split-Path -Leaf -Path $project )
    }
}

$projectExists = ($project -ne "" -and (Test-Path $project))

$onlyOneFolder = $false

if ($project -eq "") {
    Write-Host "Will run on all projects because you didn't specify a project using -project or -folder or -only."
} else {
    if ($projectExists) {
        Write-Host "Project (subdirectory) = ""$project"""
        $onlyOneFolder = $true
    }
    else {
        if ($AllIfFolderDoesntExist) { 
            Write-Host "Will run on all projects because you specified -all (-AllIfFolderDoesntExist) and the specified project subdirectory $project doesn't exist."
        }
        else {
            Write-Host "The specified project subdirectory $project doesn't exist. Specify -all (-AllIfFolderDoesntExist) or don't specify -project to regenerate all."
            $onlyOneFolder = $true
        }
    }
}

# BEGIN MAIN SCRIPT

# foreach(let $_: folder in $BaseDirectory)
Get-ChildItem -Directory -Exclude .*, _* | ForEach-Object { 
    $name = $_.Name # The name of a project is its folder's name.

    $pathGeneratedFile = GetPathGeneratedFile -name $name
    $pathMainFile = GetPathMainFile -name $name
    $relativePathGeneratedFile = GetPathGeneratedFile -name $name -relative $true
    $reverseRelativePathMainFile = GetPathMainFile -name $name -reverseRelative $true

    if ($onlyOneFolder -and $name -ne $project) {
        Write-Host "Skipped $name"
    }
    else {

        Write-Host "`nPlan to write the following references to the file " -NoNewline
        Write-Host $pathGeneratedFile -ForegroundColor Cyan

        $fileContent = generatedContent -path $_  -rootPath $reverseRelativePathMainFile
        if (
            ($fileContent -ne "") -and -not (
                (Test-Path $pathGeneratedFile) -and
                ($fileContent -eq (Get-Content $pathGeneratedFile -Encoding utf8 -Raw)[0])
            )
        ){
            $fileContent | Out-File $pathGeneratedFile -Encoding utf8
        }
    }

    # Generate main file from template for new projects, or overwrite for the specified project
    if ((
            $RenewMainFile -and
            $name -eq $project
        ) -or (
            -not (Test-Path $pathMainFile) -and
            (getIncludedTexFiles $_ ).Length -gt 0
        )) {
        MakeNewRootFile -name $name -contentFilePath $relativePathGeneratedFile
    }
}

# Save Log file from being overwritten by quick rerender
if ($saveLog) {

    $legacyPathMainFile = "./$name.tex"
    if(Test-Path $legacyPathMainFile){
        $logfile = "./out/$project.log"
    }
    else{
        $logfile = "./$project/out/$project\.log"
    }
    $destination = "./$project/.log"

    if ((Test-Path $logfile) -and (Test-Path $project)) {
        Copy-Item $logfile -Destination $destination
    }
}
