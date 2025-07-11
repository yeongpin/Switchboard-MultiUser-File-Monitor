@echo off
setlocal enabledelayedexpansion

rem 設置錯誤處理
set "error_occurred=0"

rem 獲取當前目錄路徑和名稱
set "current_path=%CD%"
for %%I in ("%CD%") do set "folder_name=%%~nxI"

echo Current folder: %folder_name%
echo Current path: %current_path%

rem 檢查 Sandbox 目錄是否存在
if not exist "%current_path%\Sandbox" (
    echo [ERROR] Sandbox directory not found at: %current_path%\Sandbox
    set "error_occurred=1"
    goto :error_exit
)

rem 定義網絡驅動器映射
set "drives=J K L M"
set "ips=51 52 53 54"

rem 創建驅動器映射數組
set "i=0"
for %%d in (%drives%) do (
    set /a "i+=1"
    for %%i in (!i!) do (
        set "drive_map[%%i]=%%d"
    )
)

rem 檢查並建立網絡連接
set "i=0"
for %%n in (%ips%) do (
    set /a "i+=1"
    for %%i in (!i!) do set "current_drive=!drive_map[%%i]!"
    
    if not exist "!current_drive!:\" (
        echo [INFO] Mapping network drive !current_drive!: to \\192.168.5.%%n...
        
        rem 根據IP選擇正確的共享文件夾名稱
        if "%%n"=="51" set "share=LeftD"
        if "%%n"=="52" set "share=MiddleD"
        if "%%n"=="53" set "share=RightD"
        if "%%n"=="54" set "share=TopD"
        
        net use !current_drive!: \\192.168.5.%%n\!share! b8@0$FbF /user:vda /persistent:yes >nul 2>&1
        
        if not exist "!current_drive!:\" (
            echo [ERROR] Failed to map drive !current_drive!: - skipping...
            set "skip_drive[%%i]=1"
        )
    )
)

echo.
echo Starting Sandbox content synchronization...
echo Source: %current_path%\Sandbox
echo.

rem 首先複製到本地 Content 目錄
echo Copying to local Content directory...
set "local_content=%current_path%\Content"
if not exist "%local_content%" (
    echo [ERROR] Local Content directory not found at: %local_content%
    set "error_occurred=1"
) else (
    robocopy "%current_path%\Sandbox" "%local_content%" /E /R:3 /W:5 /MT:8 /IS /IT /TEE /ETA /NDL /NC /BYTES /256 /DCOPY:DAT
    
    if !errorlevel! leq 8 (
        echo [SUCCESS] Completed copying to local Content
    ) else (
        echo [ERROR] Failed copying to local Content
        set "error_occurred=1"
    )
    echo ============================================================
)

rem 依序執行遠程複製操作
set "i=0"
for %%n in (%ips%) do (
    set /a "i+=1"
    for %%i in (!i!) do (
        if not defined skip_drive[%%i] (
            set "current_drive=!drive_map[%%i]!"
            echo.
            echo Copying to !current_drive!: ^(192.168.5.%%n^)...
            
            rem 確保目標 Content 目錄存在
            set "target_content=!current_drive!:\UnrealProjects\%folder_name%\Content"
            if not exist "!target_content!" (
                echo [ERROR] Content directory not found at: !target_content!
                set "error_occurred=1"
                continue
            )
            
            rem 使用 robocopy 進行複製，並顯示詳細進度
            robocopy "%current_path%\Sandbox" "!target_content!" /E /R:3 /W:5 /MT:8 /IS /IT /TEE /ETA /NDL /NC /BYTES /256 /DCOPY:DAT
            
            if !errorlevel! leq 8 (
                echo [SUCCESS] Completed copying to !current_drive!: ^(192.168.5.%%n^)
            ) else (
                echo [ERROR] Failed copying to !current_drive!: ^(192.168.5.%%n^)
                set "error_occurred=1"
            )
            echo ============================================================
        )
    )
)

goto :normal_exit

:error_exit
echo.
echo [ERROR] Script execution failed
set "error_occurred=1"

:normal_exit
echo.
if %error_occurred%==1 (
    echo Script completed with errors
) else (
    echo Script completed successfully
)
echo Script will close in 2 seconds...
timeout /t 2 >nul
exit /b %error_occurred% 