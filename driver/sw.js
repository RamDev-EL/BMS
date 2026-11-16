const C="bms-driver-v3",A=["/driver/","/driver/index.html","/driver/driver.js","/driver/manifest.json","/driver/icon.svg"];
self.addEventListener("install",e=>e.waitUntil(caches.open(C).then(c=>c.addAll(A))));
self.addEventListener("fetch",e=>{const u=new URL(e.request.url);if(u.pathname.startsWith("/api/"))return;
 e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)))});
