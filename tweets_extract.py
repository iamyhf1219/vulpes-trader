new_tab("https://x.com/search?q=lana%20trading%20agent%20design&src=typed_query&f=live")
wait_for_load(8000)
tweets = js("Array.from(document.querySelectorAll('[data-testid=\"tweetText\"]')).slice(0,10).map(t=>t.innerText).join('\\n---\\n')")
print(tweets)
