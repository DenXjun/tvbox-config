// ========================================================
// TC鸟 tc.niao.com - TVBox 规则 v13
// 按「视频干净浏览器V3.0」油猴脚本抓取逻辑 1:1 移植：
//   列表: html.split('<div class="video-item">') + 正则提取
//   详情: data-video_title + config='{...}' JSON → cfg.video.url
//   搜索: POST /index/search_article?word=KEY (keyword 那个)
// 分类: 只保留首页一个分类（用户要求）
// 字段结构: 复刻「网易公版」（用户设备确认可用）
// ========================================================

var rule = {
    title: 'TC鸟',
    host: 'https://r1mqi.fohfwjlg.cc',
    homeUrl: '/',
    url: '/page/fypage/',
    class_name: '最新视频',
    class_url: 'home',
    searchUrl: '/index/search_article?word=**&page=fypage',
    searchable: 1,
    quickSearch: 1,
    headers: {
        'User-Agent': 'MOBILE_UA'
    },
    timeout: 30000,
    limit: 20,
    play_parse: true,
    lazy: 'js:input={jx:0,url:input,parse:0}',

    // 首页/分类列表：脚本 parseList 逻辑
    推荐: 'js:var html=request(input);var list=[];var parts=html.split(\'<div class="video-item">\');for(var i=1;i<parts.length;i++){var block=parts[i].substring(0,2000);var hm=block.match(/href="(\\/archives\\/\\d+\\/)"/);if(!hm)continue;var tm=block.match(/alt="([^"]+)"/);var t=tm?tm[1]:hm[1];var img="";var im=block.match(/src="(https?:\\/\\/[^"]+)"/);if(im)img=im[1];list.push({vod_id:HOST+hm[1],vod_name:t,vod_pic:img,vod_remarks:"TC鸟"});}VODS=list;',
    一级: 'js:var html=request(input);var list=[];var parts=html.split(\'<div class="video-item">\');for(var i=1;i<parts.length;i++){var block=parts[i].substring(0,2000);var hm=block.match(/href="(\\/archives\\/\\d+\\/)"/);if(!hm)continue;var tm=block.match(/alt="([^"]+)"/);var t=tm?tm[1]:hm[1];var img="";var im=block.match(/src="(https?:\\/\\/[^"]+)"/);if(im)img=im[1];list.push({vod_id:HOST+hm[1],vod_name:t,vod_pic:img,vod_remarks:"TC鸟"});}VODS=list;',

    // 详情：脚本 parseArticleVideos 逻辑（内页视频）
    二级: 'js:var html=request(input);var videos=[];var titleRe=/data-video_title="([^"]+)"/g;var titles=[];var tm;while((tm=titleRe.exec(html))!==null){titles.push(tm[1]);}var configRe=/config=\'([^\']+)\'/g;var m;var ti=0;while((m=configRe.exec(html))!==null){try{var cfg=JSON.parse(m[1]);if(cfg.video&&cfg.video.url){var nm=(titles[ti]||("视频"+(videos.length+1)));videos.push(nm+"$"+cfg.video.url);}}catch(e){}ti++;}var nm2=html.match(/<h1[^>]*>([^<]+)<\\/h1>/);var vn=nm2?nm2[1].replace(/^\\s+|\\s+$/g,""):(titles[0]||"文章播放");var pu=videos.join("#");VOD={vod_id:input,vod_name:vn,vod_pic:"",vod_remarks:pu?("共"+videos.length+"个视频"):"本文无视频",vod_play_from:pu?"TC鸟":"提示",vod_play_url:pu||"无视频$$$"};',

    // 搜索：脚本 searchOnline 逻辑（POST /index/search_article, word=KEY）
    搜索: 'js:var d=[];var resp=post(HOST+"/index/search_article",{body:"word="+encodeURIComponent(KEY)+"&page=1&oauth_type=h5"});var data=null;try{data=JSON.parse(resp);}catch(e){}function pickHtml(hs){var r=[];var ps=hs.split(\'<div class="video-item">\');for(var i=1;i<ps.length;i++){var b=ps[i].substring(0,2000);var h=(b.match(/href="(\\/archives\\/\\d+\\/)"/)||[])[1];if(!h)continue;r.push({title:(b.match(/alt="([^"]+)"/)||[])[1]||h,url:HOST+h});}return r;}function pickArr(arr){var r=[];for(var i=0;i<arr.length;i++){var x=arr[i];var href=x.url||x.href||x.article_url;if(!href&&x.id){href="/archives/"+x.id+"/";}if(href&&href.indexOf("http")!==0){href=HOST+href;}r.push({title:x.title||x.name||x.article_title,url:href});}return r;}var items=[];if(data){var dt=data.data||data.result||data;if(typeof dt==="string"){items=pickHtml(dt);}else if(Array.isArray(dt)){items=pickArr(dt);}else if(dt.list){items=pickArr(dt.list);}else if(dt.html){items=pickHtml(dt.html);}}else{items=pickHtml(resp);}for(var i=0;i<items.length;i++){d.push({title:items[i].title,img:"",content:"",desc:"",url:items[i].url});}setResult(d);'
}
