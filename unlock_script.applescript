on run
	set pw to ""
	try
		set pw to (do shell script "cat /tmp/unlock_pw.txt")
	end try
	
	if pw is "" then
		display dialog "输入测试密码:" default answer "" with hidden answer
		set pw to text returned of result
	end if
	
	if pw is not "" then
		tell application "System Events"
			tell process "loginwindow"
				set frontmost to true
			end tell
			delay 0.5
			keystroke pw
			delay 0.2
			keystroke return
		end tell
	end if
end run
