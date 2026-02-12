; Inno Setup 6 – DokuCheck PRO
; Sestavení: iscc installer_config.iss (po předchozím PyInstaller buildu)
; Výstup: setup.exe v Output/

#define MyAppId "B8E7F2A3-4C1D-4E56-9A0B-3F2C8D1E5A6B"
#define MyAppName "DokuCheck PRO"
#define MyAppVersion "1.2.0"
#define MyAppPublisher "Ing. Martin Cieślar"
#define MyAppURL "https://www.dokucheck.cz"
#define BuildDir "dist\DokuCheckPRO"

[Setup]
AppId={{#MyAppId}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\DokuCheckPRO
DefaultGroupName={#MyAppName}
AllowNoIcons=yes
OutputDir=Output
OutputBaseFilename=DokuCheckPRO_Setup_{#MyAppVersion}
; Ikona instalátoru (odkomentujte, až máte logo\logo.ico nebo app_icon.ico):
; SetupIconFile=logo\logo.ico
UninstallDisplayIcon={app}\DokuCheckPRO.exe
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=dialog
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Pro digitální certifikaci (Microsoft Authenticode) – doplňte příkaz od certifikační autority:
; SignTool=signtool sign /tr http://timestamp.digicert.com /td sha256 /fd sha256 /f "path\to\cert.pfx" /p "password" $f
SignTool=
; Verze pro Windows (zobrazení v Properties)
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
; Celá složka z PyInstaller (onedir) včetně exe a závislostí
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

[UninstallDelete]
; Config a logy uživatele zůstávají v AppData\PDF DokuCheck Agent – nemažeme je při odinstalaci
; Type: filesandordirs; Name: "{localappdata}\PDF DokuCheck Agent"

[Code]
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
