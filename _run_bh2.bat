@echo off
browser-harness -c "new_tab('https://x.com/zaijin338191/status/2048769757571375110'); wait_for_load(10000); js('window.scrollTo(0, 800)'); wait_for_load(3000); var t=js('Array.from(document.querySelectorAll(\"[data-testid=tweetText]\")).map(function(t,i){return t.innerText}).join(\"\\n===\\n\")'); print(t);"
