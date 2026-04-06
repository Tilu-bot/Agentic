; Inno Setup 6 Script — Agentic Desktop App Installer
; ======================================================
; Produces a single "Agentic-Setup.exe" installer that:
;   • Shows a multi-step wizard (Welcome → License → Directory → Shortcuts → Install → Finish)
;   • Copies the PyInstaller dist/Agentic/ output to Program Files\Agentic
;   • Creates a Desktop shortcut and a Start Menu entry
;   • Registers a proper Add/Remove Programs entry with an Uninstaller
;
; Prerequisites (Windows only):
;   1. Install Inno Setup 6  https://jrsoftware.org/isdl.php
;   2. Build PyInstaller bundle:
;        cd agentic-app
;        pyinstaller agentic.spec
;   3. Compile this script:
;        iscc setup.iss
;      or open it in the Inno Setup IDE and press Compile (F9).
;
; Output: installer\Agentic-Setup.exe

#define AppName      "Agentic"
#define AppVersion   "1.0.0"
#define AppPublisher "Tilu-bot"
#define AppURL       "https://github.com/Tilu-bot/Agentic"
#define AppExeName   "Agentic.exe"
; PyInstaller writes its output here (relative to setup.iss location)
#define SourceDir    "dist\Agentic"

[Setup]
; ── Basic metadata ──────────────────────────────────────────────────────────
AppId={{C7EE536B-66FC-47AB-83BE-67285025D3CE}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
AppPublisherURL={#AppURL}
AppSupportURL={#AppURL}/issues
AppUpdatesURL={#AppURL}/releases

; ── Installation paths ──────────────────────────────────────────────────────
DefaultDirName={autopf}\{#AppName}
DefaultGroupName={#AppName}
; Disabling admin-only install allows per-user installs without UAC escalation
; (comment out to force machine-wide install requiring admin)
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; ── Output ──────────────────────────────────────────────────────────────────
OutputDir=installer
OutputBaseFilename=Agentic-Setup
SetupIconFile=assets\icon.ico
Compression=lzma2/ultra64
SolidCompression=yes
InternalCompressLevel=ultra64

; ── Wizard appearance ───────────────────────────────────────────────────────
WizardStyle=modern
WizardSizePercent=120
ShowLanguageDialog=no

; ── Windows version requirements ────────────────────────────────────────────
MinVersion=10.0
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible

; ── Uninstaller ─────────────────────────────────────────────────────────────
UninstallDisplayIcon={app}\{#AppExeName}
UninstallDisplayName={#AppName}
CreateUninstallRegKey=yes

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";     Description: "Create a &Desktop shortcut";          GroupDescription: "Additional shortcuts:"; Flags: checked
Name: "startmenuicon";   Description: "Create a &Start Menu shortcut";       GroupDescription: "Additional shortcuts:"; Flags: checked
Name: "quicklaunchicon"; Description: "Create a &Quick Launch shortcut";     GroupDescription: "Additional shortcuts:"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Copy the entire PyInstaller output folder
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Start Menu
Name: "{group}\{#AppName}";       Filename: "{app}\{#AppExeName}"; Tasks: startmenuicon
Name: "{group}\Uninstall {#AppName}"; Filename: "{uninstallexe}";

; Desktop
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: desktopicon

; Quick Launch (Windows XP/Vista only)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#AppName}"; Filename: "{app}\{#AppExeName}"; Tasks: quicklaunchicon

[Run]
; Offer to launch the app immediately after installation
Filename: "{app}\{#AppExeName}"; Description: "Launch {#AppName} now"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Remove any files written by the app at runtime (models, cache, logs)
; Users' data directory is intentionally left intact.
Type: filesandordirs; Name: "{app}\_internal"

[Code]
// ---------------------------------------------------------------------------
// Custom wizard page: "Downloading models" notice
// ---------------------------------------------------------------------------
procedure InitializeWizard;
var
  InfoPage: TOutputMsgWizardPage;
begin
  InfoPage := CreateOutputMsgPage(
    wpSelectDir,
    'About Model Downloads',
    'Agentic downloads AI models on first use',
    'Agentic runs 100% locally — no API keys or cloud connection required.'
    + #13#10#13#10
    + 'The first time you select a model in Settings, it will be downloaded '
    + 'from HuggingFace Hub (1–15 GB depending on the model). '
    + 'Models are cached in your HuggingFace cache folder and reused on subsequent launches.'
    + #13#10#13#10
    + 'Make sure you have enough free disk space before downloading a model.'
  );
end;
