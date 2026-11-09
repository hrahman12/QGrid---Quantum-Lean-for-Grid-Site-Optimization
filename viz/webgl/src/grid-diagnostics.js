const NS='http://www.w3.org/2000/svg';
const color=p=>p>100?'#fa7081':p>90?'#ffbd4c':'#49dba6';
export function drawGridDiagnostics(container,job){
  container.replaceChildren();
  if(!job){container.textContent='Run AC physics to inspect solved bus voltages and branch loading.';return;}
  if(!job.result.converged){container.textContent='AC power flow did not converge. Inspect the violations below.';return;}
  const svg=document.createElementNS(NS,'svg');svg.setAttribute('viewBox','0 0 330 160');svg.setAttribute('aria-label','Solved pandapower network: bus voltage in per unit and branch loading');container.append(svg);
  const element=(tag,attrs,text)=>{const n=document.createElementNS(NS,tag);for(const [k,v]of Object.entries(attrs))n.setAttribute(k,String(v));if(text!==undefined)n.textContent=text;svg.append(n);return n;};
  const positions=new Map(job.nodes.map((n,i)=>[n.id,{x:165+118*Math.cos(i/job.nodes.length*2*Math.PI-Math.PI/2),y:80+55*Math.sin(i/job.nodes.length*2*Math.PI-Math.PI/2)}]));
  for(const e of job.edges){const a=positions.get(e.from),b=positions.get(e.to);element('line',{x1:a.x,y1:a.y,x2:b.x,y2:b.y,stroke:e.loading_pct===null?'#52677d':color(e.loading_pct),'stroke-width':e.kind==='transformer'?2:3,'stroke-dasharray':e.kind==='transformer'?'3 3':'none',opacity:.8});element('text',{x:(a.x+b.x)/2,y:(a.y+b.y)/2-3,fill:'#c4e0ee','font-size':6,'text-anchor':'middle'},`${e.loading_pct?.toFixed(1)??'?'}%`);}
  for(const n of job.nodes){const p=positions.get(n.id),bad=n.vm_pu===null||n.vm_pu<.95||n.vm_pu>1.05;const c=bad?'#fa7081':'#59d9ed';element('circle',{cx:p.x,cy:p.y,r:14,fill:c,opacity:.09});element('circle',{cx:p.x,cy:p.y,r:5,fill:'#102d3c',stroke:c,'stroke-width':1.5});element('text',{x:p.x,y:p.y-11,fill:'#c0d9ed','font-size':6,'text-anchor':'middle'},n.name.length>19?n.name.slice(0,17)+'…':n.name);element('text',{x:p.x,y:p.y+14,fill:c,'font-size':7,'text-anchor':'middle'},`${n.vm_pu?.toFixed(3)??'?'} pu`);}
}
