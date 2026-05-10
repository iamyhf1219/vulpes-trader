$code = @'
new_tab("https://x.com/search?q=lana%20trading%20agent%20design&src=typed_query&f=live")
wait_for_load(5000)
js("window.scrollTo(0, 500)")
wait_for_load(3000)
tweets = js('Array.from(document.querySelectorAll("[data-testid=tweetText]")).slice(0,10).map(t=>t.innerText).join("\n---\n")')
if len(tweets) > 3000: print(tweets[:3000])
else: print(tweets)
'@

browser-harness --% -c $code
