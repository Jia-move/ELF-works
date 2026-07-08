export function cache(key, value=null, seconds=3600) {
	let expire;
	const timestamp = Date.parse(new Date()) / 1000;
	if (key && value === null) {
		const storedItem = localStorage.getItem(key);
		if(storedItem != null){
			const val = JSON.parse(storedItem);
			if (timestamp >= val.timestamp) {
				console.log("===>key已失效",key)
				localStorage.removeItem(key);
				return null
			} else {
				//console.log("key未失效")
				return val.v
			}
		}
		return null;
	} else if (key && value) {
		//设置缓存
		if (!seconds) {
			expire = timestamp + (3600 * 24 * 28);
		} else {
			expire = timestamp + seconds;
		}
		localStorage.setItem(key, JSON.stringify({v:value,timestamp:expire}));
		//console.log(timestamp + "===>" ,key,value)
	} else if(typeof key == "undefined") {
		console.log("key不能空")
	}
}