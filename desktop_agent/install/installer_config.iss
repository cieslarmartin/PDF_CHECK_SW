; Inno Setup 6 – DokuCheck PRO
; Šablona pro build_installer.py: skript nahradí MyAppVersion skutečnou verzí z ui.py (BUILD_VERSION).
; Ruční build: iscc installer_config.iss (z této složky), předtím pyinstaller dokucheck.spec ze složky desktop_agent.
; Výstup: DokuCheckPRO_Setup_{verze}_{datum}.exe v této složce (build_installer.py přejmenuje).

#define MyAppId "B8E7F2A3-4C1D-4E56-9A0B-3F2C8D1E5A6B"
#define MyAppName "DokuCheck PRO"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "Ing. Martin Cieślar"
#define MyAppURL "https://www.dokucheck.cz"
; Složka z PyInstaller buildu (relativně k této složce install/): o úroveň výš, pak dist\DokuCheckPRO
#define BuildDir "..\dist\DokuCheckPRO"

[Setup]
AppId="{#MyAppId}"
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\DokuCheckPRO
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=.
OutputBaseFilename=DokuCheckPRO_Setup_{#MyAppVersion}
SetupIconFile=..\logo\logo.ico
UninstallDisplayIcon={app}\DokuCheckPRO.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; SignTool=  – pro digitální podpis doplňte např.: SignTool=signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 /f "cert.pfx" /p "heslo" $f
VersionInfoVersion={#MyAppVersion}
VersionInfoCompany={#MyAppPublisher}
VersionInfoDescription={#MyAppName} - Desktop agent pro kontrolu PDF
VersionInfoCopyright=© 2025 Ing. Martin Cieślar
VersionInfoProductName={#MyAppName}
VersionInfoProductVersion={#MyAppVersion}

[Languages]
Name: "czech"; MessagesFile: "compiler:Languages\Czech.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked

[Files]
Source: "{#BuildDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\DokuCheckPRO.exe"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\DokuCheckPRO.exe"; Tasks: desktopicon

[Run]
Filename: "{app}\DokuCheckPRO.exe"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[InstallDelete]
; Smazat starý config.yaml z AppData, aby agent při příštím startu vytvořil nový s aktuální URL (dokucheck.cz)
Type: files; Name: "{userappdata}\PDF DokuCheck Agent\config.yaml"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
