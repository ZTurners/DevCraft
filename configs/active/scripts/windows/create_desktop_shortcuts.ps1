[CmdletBinding()]
param([string]$Workspace = $PSScriptRoot)
$ErrorActionPreference = 'Stop'
$Workspace = (Resolve-Path -LiteralPath $Workspace).Path
$desktop = [Environment]::GetFolderPath('Desktop')
$publicDesktop = [Environment]::GetFolderPath('CommonDesktopDirectory')
$shell = New-Object -ComObject WScript.Shell
$existing = @(foreach ($folder in @($desktop, $publicDesktop) | Select-Object -Unique) {
    if (Test-Path -LiteralPath $folder) {
        foreach ($file in Get-ChildItem -LiteralPath $folder -Filter '*.lnk' -File) {
            [pscustomobject]@{ Path = $file.FullName; Shortcut = $shell.CreateShortcut($file.FullName) }
        }
    }
})
$launchers = @(
    @{ Id = 'cmd'; Name = 'CMD Dev'; Icon = 'cmd-dev.ico' }
    @{ Id = 'codex_app'; Name = 'Codex App Dev'; Icon = 'codex-dev.ico' }
    @{ Id = 'codex_cli'; Name = 'Codex CLI Dev'; Icon = 'codex-dev.ico' }
    @{ Id = 'dsh'; Name = 'DeepSeek Harness Dev'; Icon = 'dsh-dev.ico' }
    @{ Id = 'vscode'; Name = 'VS Code Dev'; Icon = 'vscode-dev.ico' }
    @{ Id = 'zcode'; Name = 'ZCode Dev'; Icon = 'zcode-dev.ico' }
)
# Validate every target before changing any desktop shortcuts.
foreach ($launcher in $launchers) {
    $launcher.Target = Join-Path $Workspace ('active_with_' + $launcher.Id + '.windows.bat')
    $launcher.IconPath = Join-Path $Workspace ('.icons\' + $launcher.Icon)
    foreach ($file in @($launcher.Target, $launcher.IconPath)) {
        if (-not (Test-Path -LiteralPath $file -PathType Leaf)) { throw "Missing shortcut asset: $file" }
    }
}
foreach ($launcher in $launchers) {
    $matches = @($existing | Where-Object {
        $_.Shortcut.TargetPath -ieq $launcher.Target -or
        ($_.Shortcut.TargetPath -imatch '\\(cmd|powershell|pwsh)\.exe$' -and
         $_.Shortcut.Arguments.IndexOf($launcher.Target, [StringComparison]::OrdinalIgnoreCase) -ge 0)
    })
    if ($matches.Count -gt 0) {
        foreach ($match in $matches) {
            $match.Shortcut.IconLocation = $launcher.IconPath + ',0'
            $match.Shortcut.Save()
            Write-Output ('Updated icon: ' + $match.Path)
        }
    } else {
        $link = Join-Path $desktop ($launcher.Name + '.lnk')
        if (Test-Path -LiteralPath $link) { throw "Shortcut name is already in use: $link" }
        $shortcut = $shell.CreateShortcut($link)
        $shortcut.TargetPath = $launcher.Target
        $shortcut.WorkingDirectory = $Workspace
        $shortcut.Description = 'Start ' + $launcher.Name + ' with the DevCraft environment'
        $shortcut.IconLocation = $launcher.IconPath + ',0'
        $shortcut.Save()
        Write-Output ('Created: ' + $link)
    }
}
