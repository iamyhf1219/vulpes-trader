@echo off
browser-harness -c "new_tab('https://x.com/zaijin338191/status/2048769757571375110'); wait_for_load(10000); js('window.scrollTo(0, 800)'); wait_for_load(3000); capture_screenshot('zaijin_tweet.png'); print('DONE')"
