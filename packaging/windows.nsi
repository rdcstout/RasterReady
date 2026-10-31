Unicode true
RequestExecutionLevel user
SetCompressor /SOLID lzma
!include "MUI2.nsh"
!include "x64.nsh"

Name "RasterReady"
OutFile "${OUTPUT_FILE}"
InstallDir "$LOCALAPPDATA\Programs\RasterReady"
Var Upgrade
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\RasterReady"
!define MUI_ABORTWARNING
!define MUI_ICON "${PRODUCT_ICON}"
!define MUI_UNICON "${PRODUCT_ICON}"
!define MUI_WELCOMEPAGE_TEXT "This will install RasterReady for your Windows account. Close RasterReady before continuing."
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "English"

Function .onInit
  SetShellVarContext current
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP "RasterReady requires 64-bit Windows."
    Abort
  ${EndIf}
  ; Fixed per-user destination also constrains command-line /D overrides.
  StrCpy $INSTDIR "$LOCALAPPDATA\Programs\RasterReady"
  StrCpy $Upgrade 0
  IfFileExists "$INSTDIR\*" 0 fresh_install
  ReadRegStr $0 HKCU "${UNINSTALL_KEY}" "InstallLocation"
  StrCmp $0 $INSTDIR 0 folder_in_use
  IfFileExists "$INSTDIR\Uninstall.exe" 0 folder_in_use
  StrCpy $Upgrade 1
  Goto fresh_install
folder_in_use:
  MessageBox MB_ICONSTOP "RasterReady's installation folder is already in use. Rename that folder or remove the previous installation before continuing."
  Abort
fresh_install:
FunctionEnd

Section "RasterReady"
  SetShellVarContext current
  ; Only modify the old installation after the user chooses Install.
  StrCmp $Upgrade 1 0 copy_payload
  ExecWait '"$INSTDIR\Uninstall.exe" /S _?=$INSTDIR' $0
  StrCmp $0 0 copy_payload
  MessageBox MB_ICONSTOP "The previous installation could not be removed. Close RasterReady and try again."
  SetErrorLevel 1
  Abort
copy_payload:
  SetOverwrite on
  ClearErrors
  !include "${INSTALL_FILES}"
  IfErrors install_failed
  WriteUninstaller "$INSTDIR\Uninstall.exe"
  IfErrors install_failed
  CreateDirectory "$SMPROGRAMS\RasterReady"
  CreateShortcut "$SMPROGRAMS\RasterReady\RasterReady.lnk" "$INSTDIR\RasterReady.exe"
  CreateShortcut "$SMPROGRAMS\RasterReady\Uninstall RasterReady.lnk" "$INSTDIR\Uninstall.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayName" "RasterReady"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "Publisher" "Extrusion Therapy"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\RasterReady.exe"
  WriteRegStr HKCU "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKCU "${UNINSTALL_KEY}" "NoRepair" 1
  IfErrors install_failed
  Goto install_done
install_failed:
  MessageBox MB_ICONSTOP "Installation could not finish. Close RasterReady, check available disk space and run this installer again."
  SetErrorLevel 1
  Abort
install_done:
SectionEnd

Function un.onInit
  SetShellVarContext current
  StrCpy $INSTDIR "$LOCALAPPDATA\Programs\RasterReady"
FunctionEnd

Section "Uninstall"
  SetShellVarContext current
  ClearErrors
  ; Generated exact paths only. Unknown files and nonempty directories survive.
  !include "${UNINSTALL_FILES}"
  IfErrors uninstall_failed
  !include "${REMOVE_DIRECTORIES}"
  ; Unknown files keep their nonempty directories, which is not an error.
  ClearErrors
  Delete "$SMPROGRAMS\RasterReady\RasterReady.lnk"
  Delete "$SMPROGRAMS\RasterReady\Uninstall RasterReady.lnk"
  RMDir "$SMPROGRAMS\RasterReady"
  DeleteRegKey HKCU "${UNINSTALL_KEY}"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir "$INSTDIR"
  Goto uninstall_done
uninstall_failed:
  MessageBox MB_ICONSTOP "Some application files are in use. Close RasterReady and run the uninstaller again."
  SetErrorLevel 1
  Abort
uninstall_done:
SectionEnd
