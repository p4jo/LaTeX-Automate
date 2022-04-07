param(
    [Alias("b", "root")]
    [string] $BaseDirectory = "",

    [Alias( "f", "folder", "o","only", "p")]
    [string] $project = "",

    [Alias("all")]
    [switch] $AllIfFolderDoesntExist = $false, # Im Zweifel alle

    [Alias("overwrite", "renew", "r")]
    [switch] $RenewMainFile = $false,

    [Alias("a")]
    [string] $author = "Johannes Heißler",
    
    [Alias("log", "l")]
    [switch] $saveLog = $false,

    [Alias("h", "help", "-help")]
    [switch] $getHelp = $false
)

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
    $allProjectTexFiles = (Get-ChildItem -Path $path -Filter "*.tex" -Exclude $excludeFile, _*, *_ -Recurse)
    $ProjectTexFiles = $allProjectTexFiles | Where-Object {-not (Test-Path (-join($_.Directory.FullName, "\.texignore")))} 
    
    if($log) {
        $nonProjectFiles = $allProjectTexFiles | Where-Object {$ProjectTexFiles -notcontains $_}
        $nonProjectFiles | ForEach-Object {
                Write-Host "`tSkipped`t" -ForegroundColor Red -NoNewline
                Write-Host "`"$_`"." -ForegroundColor Gray
            }
        $ProjectTexFiles | ForEach-Object {
                Write-Host "`tAdded`t" -ForegroundColor Green -NoNewline
                Write-Host "`"$_`"." -ForegroundColor Gray
            }
    }

    return $ProjectTexFiles
}

function inputGeneratedContent ($path, $rootPath, $excludeFile) {
    
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
    $PfadHauptdatei = "./$name.tex"
    Write-Host "Will write a new main file for $name. The old one will be backed up." -ForegroundColor Yellow
    if(Test-Path "$PfadHauptdatei.bak"){
        Remove-Item "$PfadHauptdatei.bak"
    }
    if(Test-Path $PfadHauptdatei){
        Rename-Item $PfadHauptdatei "$PfadHauptdatei.bak"
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


% \input{$name/_commands.tex}   


\hypersetup{
    % pdfsubject  = {$name},
    % pdfkeywords = {$name}
}

\addbibresource{./$name/Referenzen.bib}

\begin{document}
%%% Titelseite hier (nur, wenn nicht simpleTitle als Option gesetzt wurde) :
% \input{$name/_Titelseite.tex}

\Inhaltsverzeichnis

%%% Inhalt hier:

\input{$name/$contentFileName}

\end{document}" | Out-File -FilePath $PfadHauptdatei -Encoding utf8 
           
}

# SKRIPT START

if ($BaseDirectory -ne ""){
    Set-Location $BaseDirectory
}
else{
    $BaseDirectory = Get-Location
}

Write-Host "This is JHAutomate." -ForegroundColor Green
Write-Host "Base directory = ""$BaseDirectory"", Author for new main files: ""$author""."


$projectExists = (Test-Path $project)
if ($project -eq "") {
    $onlyOneFolder = $false
    Write-Host "Will run on all projects because you didn't specify a project using -project or -folder or -only."
} else {
    $project = $project.Substring($project.LastIndexOf('/')+1).Replace(".tex","")
    if ($projectExists) {
        Write-Host "Project (subdirectory) = ""$project"""
    }
    else {
        if ($AllIfFolderDoesntExist) { 
            Write-Host "Will run on all projects because you specified -all (-AllIfFolderDoesntExist) and the specified project subdirectory $project doesn't exist."
        }
        else {
            Write-Host "The specified project subdirectory $project doesn't exist. Specify -all (-AllIfFolderDoesntExist) or don't specify -project to regenerate all."
        }        
        $onlyOneFolder =  -not $AllIfFolderDoesntExist
    }
}

# ANFANG 

# foreach(Ordner $_ in hier)
Get-ChildItem -Directory -Exclude .*, _* | 
ForEach-Object { 
    $name = $_.Name
    $Dateiname = -join($name,"_generated.tex")

    if ($onlyOneFolder -and $name -ne $project) {
        Write-Host "Skipped $name"
    }
    else {
        $PfadInnereAuflistungsTex = -join("./", $name, "/", $Dateiname)

        Write-Host "`nPlan to write the following references to the file " -NoNewline
        Write-Host $PfadInnereAuflistungsTex -ForegroundColor Cyan

        $fileContent = inputGeneratedContent -path $_ -excludeFile $Dateiname -rootPath "../$name.tex"
        if (
            ($fileContent -ne "") -and -not (
                (Test-Path $PfadInnereAuflistungsTex) -and
                ($fileContent -eq (Get-Content $PfadInnereAuflistungsTex -Encoding utf8 -Raw)[0])
            )
        ){
            $fileContent | Out-File $PfadInnereAuflistungsTex -Encoding utf8
        }
    }
    # Schreibe, wenn nicht vorhanden, eine Hauptdatei
    if ((
            $RenewMainFile -and
            $name -eq $project
        ) -or (
            -not (Test-Path "./$name.tex") -and
            (getIncludedTexFiles $_ ).Length -gt 0
        )) {
        MakeNewRootFile -name $name -contentFileName $Dateiname
    }
}