// Design-only. Isolated loopback service; synthetic fixture and in-memory tasks only.
const http=require('node:http'), fs=require('node:fs'), path=require('node:path'), crypto=require('node:crypto');
const ROOT=__dirname, FIX=JSON.parse(fs.readFileSync(path.join(ROOT,'assets/fixture.json'),'utf8'));
const ANNOTATION_FILE=path.join(ROOT,'review-annotations.json');
const tasks=new Map();
const aliases={'default':'empty','new':'empty','generate-ready':'saved','processing':'p3','result':'success','error':'failed','blocked':'insufficient','refresh':'restored','history':'history-p1'};
function blank(){return {name:'',phone:'',email:'',location:'',target:''};}
function create(sc='empty'){
 sc=aliases[sc]||sc;
 const points={p1:2200,p2:6500,p3:13600,p4:31000,success:37000,failed:21000,'failed-p4':33000,insufficient:6500,cancel:15000,cancelled:15000,'history-p1':17000,'history-p2':17000,restored:15500,menu:15000,experiences:15000,privacy:15000,records:37000};
 const filled=sc!=='empty';const t={id:crypto.randomUUID(),revision:0,op:0,identity:filled?structuredClone(FIX.identity):blank(),jd:filled?FIX.jd:'',status:filled?'saved':'empty',elapsed:points[sc]||0,anchor:Date.now(),paused:true,scenario:sc,hasFacts:true,selectedExperience:'exp-1',edits:{},records:[],inputSeq:0};
 if(sc in points)t.status='running';
 if(sc==='success'||sc==='records'){t.status='success';t.records=[{id:'sample',title:FIX.identity.target}];}
 if(sc==='failed'||sc==='failed-p4')t.status='failed';
 if(sc==='insufficient'){t.status='blocked';t.hasFacts=false;}
 if(sc==='cancelled')t.status='cancelled';
 tasks.set(t.id,t);return t;
}
function snapshot(t){
 if(t.status==='running'&&!t.paused){t.elapsed+=Date.now()-t.anchor;t.anchor=Date.now();if(t.elapsed>=36000){t.status='success';t.elapsed=36000;if(!t.records.length)t.records.push({id:'sample',title:t.identity.target||'岗位简历'});}}
 const phase=t.elapsed<5000?'p1':t.elapsed<9000?'p2':t.elapsed<28000?'p3':'p4';
 let factCount=t.elapsed<9000?0:Math.min(5,Math.max(0,Math.floor((t.elapsed-9000)/3500)));
 if(t.status==='failed'&&t.scenario!=='failed-p4')factCount=2;
 if(t.retrying)factCount=Math.max(2,factCount);
 return {...t,phase,factCount,step:['empty','saved','saving'].includes(t.status)?1:phase==='p1'||phase==='p2'?2:phase==='p3'?3:4,jdCount:Math.min(5,Math.floor(t.elapsed/850)),recallCount:!t.hasFacts?0:Math.min(2,Math.max(0,Math.floor((t.elapsed-5000)/1500))),reasonChars:Math.floor((t.elapsed-9000)%3500/45)};
}
const mime={'.html':'text/html; charset=utf-8','.css':'text/css; charset=utf-8','.js':'text/javascript; charset=utf-8','.mjs':'text/javascript; charset=utf-8','.json':'application/json; charset=utf-8','.pdf':'application/pdf','.docx':'application/vnd.openxmlformats-officedocument.wordprocessingml.document','.png':'image/png','.svg':'image/svg+xml','.ttf':'font/ttf'};
function send(res,status,data){res.writeHead(status,{'Content-Type':'application/json; charset=utf-8','Cache-Control':'no-store'});res.end(JSON.stringify(data));}
function readAnnotations(){try{const x=JSON.parse(fs.readFileSync(ANNOTATION_FILE,'utf8'));return Array.isArray(x)?x:[];}catch(e){if(e.code==='ENOENT')return [];throw e;}}
function cleanAnnotations(value){if(!Array.isArray(value)||value.length>500)throw Error('批注数据格式无效');return value.map(a=>({id:String(a.id||'').slice(0,80),text:String(a.text||'').slice(0,4000),target:{selector:String(a.target?.selector||'').slice(0,1000),label:String(a.target?.label||'').slice(0,240),tag:String(a.target?.tag||'').slice(0,40)},context:{route:String(a.context?.route||'').slice(0,80),scenario:String(a.context?.scenario||'').slice(0,80),theme:String(a.context?.theme||'').slice(0,8),viewport:String(a.context?.viewport||'').slice(0,40),url:String(a.context?.url||'').slice(0,1000)},createdAt:String(a.createdAt||'').slice(0,80),updatedAt:String(a.updatedAt||'').slice(0,80),status:a.status==='resolved'?'resolved':'open'})).filter(a=>a.id&&a.text&&a.target.selector);}
function writeAnnotations(value){const data=cleanAnnotations(value),tmp=ANNOTATION_FILE+'.tmp';fs.writeFileSync(tmp,JSON.stringify(data,null,2),'utf8');fs.renameSync(tmp,ANNOTATION_FILE);return data;}
const server=http.createServer(async(req,res)=>{
 try{
 const url=new URL(req.url,'http://localhost');
 if(url.pathname==='/favicon.ico'){res.writeHead(204);return res.end();}
 if(url.pathname.startsWith('/design/')){
  if(req.headers.origin&&!/^http:\/\/(127\.0\.0\.1|localhost):\d+$/.test(req.headers.origin))return send(res,403,{error:'origin'});
  let raw='';for await(const chunk of req){raw+=chunk;if(raw.length>50000)return send(res,413,{error:'too large'});}
  const body=raw?JSON.parse(raw):{};
  if(url.pathname==='/design/annotations'){
   if(req.method==='GET')return send(res,200,readAnnotations());
   if(req.method==='POST')return send(res,200,writeAnnotations(body.annotations));
   return send(res,405,{error:'method'});
  }
  if(url.pathname==='/design/tasks'&&req.method==='POST')return send(res,200,snapshot(create(body.scenario)));
  const id=url.pathname.split('/')[3], t=tasks.get(id);if(!t)return send(res,404,{error:'设计服务已重启，临时任务不在内存中。'});
  snapshot(t);
  if(req.method==='GET')return send(res,200,snapshot(t));
  if(req.method!=='POST')return send(res,405,{error:'method'});
  switch(body.action){
   case 'save':if(['empty','saved','saving'].includes(t.status)&&body.seq>=t.inputSeq){t.identity=body.identity;t.jd=body.jd;t.inputSeq=body.seq;t.revision++;t.status='saved';}break;
   case 'start':if(['empty','saved','cancelled','blocked'].includes(t.status)){if(!t.identity.name.trim()||t.jd.trim().length<30)return send(res,400,{error:'请填写姓名和完整的职位描述。'});t.op++;t.status='running';t.elapsed=0;t.paused=false;t.anchor=Date.now();}break;
   case 'pause':t.paused=!t.paused;t.anchor=Date.now();break;
   case 'advance':if(t.status==='running'){t.elapsed=t.elapsed<5000?6500:t.elapsed<9000?15000:t.elapsed<28000?31000:36000;if(t.elapsed===36000){t.status='success';t.records=[{id:'sample',title:t.identity.target||'岗位简历'}];}}break;
   case 'cancel':if(t.status==='running'&&body.op===t.op){t.status='cancelled';t.paused=true;t.op++;}break;
   case 'retry':if(t.status==='failed'){t.status='running';t.retrying=t.scenario!=='failed-p4';t.elapsed=t.retrying?16000:28000;t.paused=false;t.anchor=Date.now();t.op++;}break;
   case 'edit-input':if(t.status!=='running'){t.status='saved';t.elapsed=0;t.op++;t.paused=true;}break;
   case 'clear':if(t.status==='running')return send(res,409,{error:'请先取消当前生成。'});t.identity=blank();t.jd='';t.status='empty';t.elapsed=0;t.revision++;break;
   case 'facts':t.hasFacts=true;t.edits[body.id||'exp-1']=String(body.text||'').slice(0,4000);break;
   case 'new':if(t.status==='running')return send(res,409,{error:'请先取消当前生成。'});{const n=create('empty');n.records=t.records;n.hasFacts=t.hasFacts;n.edits=t.edits;return send(res,200,snapshot(n));}
  }
  return send(res,200,snapshot(t));
 }
 if(!['GET','HEAD'].includes(req.method)){res.writeHead(405);return res.end();}
 const rel=decodeURIComponent(url.pathname)==='/'?'index.html':decodeURIComponent(url.pathname).slice(1);
 const file=path.resolve(ROOT,rel);
 if(!file.startsWith(ROOT+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);return res.end('Not found');}
 const size=fs.statSync(file).size;let start=0,end=size-1,code=200;
 const range=req.headers.range?.match(/^bytes=(\d+)-(\d*)$/);if(range){start=+range[1];end=range[2]?Math.min(+range[2],end):end;code=206;if(start>end){res.writeHead(416);return res.end();}}
 const headers={'Content-Type':mime[path.extname(file)]||'text/plain; charset=utf-8','Cache-Control':'no-store','Content-Length':end-start+1,'Accept-Ranges':'bytes','X-Content-Type-Options':'nosniff'};
 if(code===206)headers['Content-Range']=`bytes ${start}-${end}/${size}`;
 res.writeHead(code,headers);if(req.method==='HEAD')return res.end();fs.createReadStream(file,{start,end}).pipe(res);
 }catch(e){send(res,500,{error:'设计服务暂时不可用'});}
});
server.listen(Number(process.env.DESIGN_PORT||8763),'127.0.0.1',()=>console.log('D-003 Design 工作稿 http://127.0.0.1:'+server.address().port));


