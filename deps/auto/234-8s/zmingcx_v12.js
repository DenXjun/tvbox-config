// ========================================================
// 知更鸟 zmingcx.com - TVBox 规则 v12
// 按「视频干净浏览器」油猴脚本的截取逻辑编写：
//   fetch → split 分块 → 正则提取标题/链接/图片/播放源
// 站点: WordPress(知更鸟) - 文章站
// 字段结构: 完全复刻「网易公版」（用户设备确认可用）
// 分类: 只保留一个首页分类（用户要求）
// ========================================================

var rule = {
    title: '知更鸟',
    host: 'https://r1mqi.fohfwjlg.cc',
    homeUrl: '/',
    url: '/page/fypage/',
    class_name: '最新文章',
    class_url: 'home',
    headers: {
        'User-Agent': 'MOBILE_UA'
    },
    timeout: 30000,
    limit: 20,
    play_parse: true,
    lazy: 'js:input={jx:0,url:input,parse:0}',

    // 首页推荐：抓首页 → split('<article') 分块 → 正则提取
    推荐: 'js:var html=request(input);var list=[];var parts=html.split("<article");for(var i=1;i<parts.length;i++){var p=parts[i];var hm=p.match(/href="(https:\\/\\/zmingcx\\.com\\/[^"]+\\.html)"/);if(!hm)continue;var tm=p.match(/<h2[^>]*>\\s*<a[^>]*>([^<]+)<\\/a>/);var t=tm?tm[1].replace(/^\\s+|\\s+$/g,""):"未命名";var pic="";var pm=p.match(/background-image:\\s*url\\(([^)]+)\\)/);if(pm){pic=pm[1];}else{var ds=p.match(/data-src="(https?:\\/\\/[^"]+)"/);if(ds)pic=ds[1];}list.push({vod_id:hm[1],vod_name:t,vod_pic:pic,vod_remarks:"知更鸟"});}VODS=list;',

    // 分类列表：同样截取逻辑
    一级: 'js:var html=request(input);var list=[];var parts=html.split("<article");for(var i=1;i<parts.length;i++){var p=parts[i];var hm=p.match(/href="(https:\\/\\/zmingcx\\.com\\/[^"]+\\.html)"/);if(!hm)continue;var tm=p.match(/<h2[^>]*>\\s*<a[^>]*>([^<]+)<\\/a>/);var t=tm?tm[1].replace(/^\\s+|\\s+$/g,""):"未命名";var pic="";var pm=p.match(/background-image:\\s*url\\(([^)]+)\\)/);if(pm){pic=pm[1];}else{var ds=p.match(/data-src="(https?:\\/\\/[^"]+)"/);if(ds)pic=ds[1];}list.push({vod_id:hm[1],vod_name:t,vod_pic:pic,vod_remarks:"知更鸟"});}VODS=list;',

    // 详情：抓文章页 → 正则截取 B站 iframe / MP4 直链 → 拼播放列表
    二级: 'js:var html=request(input);var videos=[];var m;var reB=/<iframe[^>]*src="(\\/\\/player\\.bilibili\\.com\\/player\\.html\\?[^"]+)"/gi;while((m=reB.exec(html))!==null){var bv=m[1].match(/bvid=([A-Za-z0-9]+)/);if(bv){videos.push("B站"+(videos.length+1)+"$https://www.bilibili.com/video/"+bv[1]);}else{videos.push("B站"+(videos.length+1)+"$https:"+m[1]);}}var reM=/(?:src|data-src)="(https?:\\/\\/[^"]*\\.mp4[^"]*)"/gi;while((m=reM.exec(html))!==null){videos.push("视频"+(videos.length+1)+"$"+m[1]);}var tm=html.match(/<h1[^>]*>([^<]+)<\\/h1>/);var name=tm?tm[1].replace(/^\\s+|\\s+$/g,""):"文章播放";var pu=videos.join("#");VOD={vod_id:input,vod_name:name,vod_pic:"",vod_remarks:pu?("共"+videos.length+"个播放源"):"本文无内嵌播放源",vod_play_from:pu?"知更鸟":"提示",vod_play_url:pu||"无视频$$$"};',

    // 搜索：站点开启搜索验证，不可用
    搜索: 'js:VODS=[]'
}
