# DeleteOldFiles.ps1
# Supprime tous les fichiers *.old dans le dossier donné et ses sous-dossiers

$targetPath = "E:\Projects\DeadBot"  # Adapte ce chemin selon ton venv final

Write-Host "Suppression des fichiers .old dans $targetPath et sous-dossiers..."

Get-ChildItem -Path $targetPath -Recurse -Include *.old -File | ForEach-Object {
    Write-Host "Suppression de $_"
    Remove-Item $_.FullName -Force
}

Write-Host "Suppression terminée."
