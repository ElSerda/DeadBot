# ------------------------------------------
# Script: Migrate_clean_DeadBot.ps1 (patched)
# Migration propre DeadBot v0.1.0 - 2025
# Backup les anciens fichiers en .old avant overwrite
# ------------------------------------------

$SRC = "E:\Projects\g-assist_deadbot"        # Chemin source (à adapter !)
$DST = "E:\Projects\DeadBot"                 # Chemin destination (à adapter !)

# Création du dossier destination si absent
if (!(Test-Path $DST)) {
    New-Item -ItemType Directory -Path $DST
}

$extensions = @(".py", ".md", ".txt", ".yaml", ".yml", ".json", ".csv", ".ini", ".cfg", ".bat", ".ps1", ".")

Get-ChildItem -Path $SRC -File -Recurse | Where-Object { $extensions -contains $_.Extension } | ForEach-Object {
    $fileContent = Get-Content $_.FullName -Raw
    if ($fileContent -like "*v0.1.0*") {
        $relPath = $_.FullName.Substring($SRC.Length).TrimStart('\','/')
        $destPath = Join-Path $DST $relPath
        $destDir = Split-Path $destPath
        if (!(Test-Path $destDir)) {
            New-Item -ItemType Directory -Path $destDir -Force
        }
        # Backup en .old si le fichier existe déjà
        if (Test-Path $destPath) {
            $oldPath = $destPath + ".old"
            Write-Host "Backup : $destPath -> $oldPath"
            Move-Item -Path $destPath -Destination $oldPath -Force
        }
        Write-Host "Copy : $($_.FullName) -> $destPath"
        Copy-Item -Path $_.FullName -Destination $destPath -Force
    }
}

Write-Host "Migration terminée !"
Write-Host "Tous les fichiers crowd (tag v0.1.0) sont copiés et anciens fichiers sauvegardés en .old dans $DST"
