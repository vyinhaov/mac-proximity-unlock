-- AppleScript to create UnlockMac Shortcut in the Shortcuts app
-- Run: osascript setup_unlock_shortcut.scpt

tell application "Shortcuts"
    activate
    delay 0.5
end tell

tell application "System Events"
    tell process "Shortcuts"
        -- Create new shortcut (Cmd+N)
        keystroke "n" using {command down}
        delay 1
        
        -- Name it
        keystroke "UnlockMac"
        delay 0.5
        keystroke return
        delay 0.5
        
        -- Add action: search for "Run AppleScript"
        keystroke "f" using {command down}
        delay 0.3
        keystroke "Run AppleScript"
        delay 0.5
        keystroke return
        delay 0.5
        
        -- Now we need to set the script content...
        -- Unfortunately full script editing via GUI is fragile
        -- Better approach: just tell the user what to do
    end tell
end tell

display dialog "Shortcut GUI automation is unreliable. Please create 'UnlockMac' shortcut manually:
1. Open Shortcuts app
2. Click + to create new
3. Search 'Run AppleScript', add it
4. Paste the script from ~/mac-proximity-unlock/unlock_script.applescript
5. Name it 'UnlockMac'
6. Save and close" buttons {"OK"} default button "OK"
