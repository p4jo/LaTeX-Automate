param(
    [Alias("b", "r", "root")]
    [string] $BaseDirectory = "",

    [Alias( "f", "folder", "o","only", "p")]
    [string] $project = "",

    [Alias("all")]
    [switch] $AllIfFolderDoesntExist = $false, # Im Zweifel alle

    [Alias("overwrite", "renew", "r")]
    [switch] $RenewMainFile = $false,

    [Alias("a")]
    [string] $author = "Johannes Heißler",
    
    [Alias("log", "l", "s", "backupLog")]
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
        [string] $excludeFile = "",
        [switch] $log = $false
    )
    $allProjectFiles = (Get-ChildItem -Path $path -Filter "*.tex" -Exclude $excludeFile, _*, *_ -Recurse)
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

function generatedContent ($path, $rootPath, $excludeFile) {
    
    $currentPath = $path.FullName.Replace("\","/")
    $texstring = ""     
    
    (getIncludedTexFiles -path $path -excludeFile $excludeFile -log $true) | #Alle tex-Dateien in allen Unterordnern anschauen, ausschließen mit _.
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

function MakeNewRootFile($name, $contentFileName) {
    $pathMainFile = "./$name.tex"
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
    simpleTitle
]
{JHPreamble} 

\RequirePackage{icomma} %macht Kommas ohne Leerzeichen danach zu Kommas ohne Abstand danach

\hypersetup{
    pdfsubject  = {$name},
    pdfkeywords = {$name}
}

\addbibresource{./$name/Referenzen.bib}

\begin{document}

%%% Titelseite hier (nur, wenn nicht simpleTitle als Option gesetzt wurde)

\Inhaltsverzeichnis

%%% Inhalt hier:

\input{$name/$contentFileName}

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

$project = $project.TrimEnd(".tex").TrimEnd('/').TrimEnd('\')

$projectExists = (Test-Path $project)

$onlyOneFolder = $false

if ($project -eq "") {
    Write-Host "Will run on all projects because you didn't specify a project using -project or -folder or -only."
} else {
    $project = $project.Substring($project.LastIndexOf('/')+1)
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
    $nameGeneratedFile = -join($name,"_generated.tex")

    if ($onlyOneFolder -and $name -ne $project) {
        Write-Host "Skipped $name"
    }
    else {
        $pathGeneratedFile = "./$name/$nameGeneratedFile"

        Write-Host "`nPlan to write the following references to the file " -NoNewline
        Write-Host $pathGeneratedFile -ForegroundColor Cyan

        $fileContent = generatedContent -path $_ -excludeFile $nameGeneratedFile -rootPath "../$name.tex"
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
            -not (Test-Path "./$name.tex") -and
            (getIncludedTexFiles $_ ).Length -gt 0
        )) {
        MakeNewRootFile -name $name -contentFileName $nameGeneratedFile
    }
}

# Save Log file from being overwritten by quick rerender
if ($saveLog) {

    $logfile = "$project.log"
    $destination = "$project\.log"

    if ((Test-Path $logfile) -and (Test-Path $project)) {
        Copy-Item $logfile -Destination $destination
    }
}
