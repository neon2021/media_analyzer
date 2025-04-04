import os
import subprocess
import sys
import time

def grant_permissions():
    """使用osascript直接授权"""
    # 获取Python解释器路径
    python_path = sys.executable
    
    # 构建AppleScript命令
    applescript = f'''
    tell application "System Events"
        -- 获取安全偏好设置
        set securityPrefs to security preferences
        
        -- 添加完全磁盘访问权限
        tell securityPrefs
            set thePrivilege to {{
                name:"Full Disk Access",
                process:process "Python",
                file:POSIX file "/Volumes",
                bundleID:"com.apple.python"
            }}
            set thePrivileges to get privileges
            if thePrivilege is not in thePrivileges then
                set privileges to thePrivileges & {{thePrivilege}}
            end if
        end tell
        
        -- 添加文件和文件夹访问权限
        tell securityPrefs
            set thePrivilege to {{
                name:"Files and Folders",
                process:process "Python",
                file:POSIX file "{os.path.expanduser('~')}",
                bundleID:"com.apple.python"
            }}
            set thePrivileges to get privileges
            if thePrivilege is not in thePrivileges then
                set privileges to thePrivileges & {{thePrivilege}}
            end if
        end tell
    end tell
    '''
    
    try:
        # 执行AppleScript
        subprocess.run(['osascript', '-e', applescript], check=True)
        print("✓ 权限已授予")
        
        # 等待系统更新权限
        time.sleep(2)
        
        # 验证权限
        try:
            os.listdir("/Volumes")
            print("✓ 权限验证成功")
            return True
        except PermissionError:
            print("⚠️ 权限验证失败")
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"⚠️ 权限授予失败: {e}")
        print("\n请手动授权：")
        print("1. 打开系统偏好设置")
        print("2. 选择'隐私与安全性'")
        print("3. 选择'完全磁盘访问权限'")
        print("4. 点击'+'按钮")
        print(f"5. 添加 Python 解释器: {python_path}")
        return False

if __name__ == "__main__":
    if grant_permissions():
        print("\n现在可以运行主程序了：")
        print("python main-002-scan_files.py")
    else:
        sys.exit(1) 