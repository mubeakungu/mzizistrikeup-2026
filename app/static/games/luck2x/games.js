(() => {
const game=window.LUCK2X_GAME, $=id=>document.getElementById(id);
const bet=()=>parseFloat($("bet").value||0), json=async(url,data)=>{const r=await fetch(url,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(data||{})});const j=await r.json();if(!r.ok||j.ok===false)throw new Error(j.error||"Request failed");return j;};
$("extra").innerHTML = game==="dice" ? `<label>Mode<select id="mode"><option value="over">Roll over</option><option value="under">Roll under</option></select></label><label>Target<input id="target" type="number" min="1" max="99" value="50"></label>` :
 game==="tower" ? `<label>Bombs<select id="bombs"><option>1</option><option>2</option><option>3</option><option>4</option></select></label>` :
 game==="mines" ? `<label>Bombs<select id="bombs">${Array.from({length:8},(_,i)=>`<option>${i+1}</option>`).join("")}</select></label>` :
 game==="wheel" ? `<label>Colour<select id="color"><option>black</option><option>red</option><option>yellow</option><option>green</option></select></label>` :
 game==="hilo" ? `` : ``;

const status=(x)=>$("status").textContent=x;
const board=(html)=>$("board").innerHTML=html;

function crashLoop(info){
  let m=1.0, start=performance.now();
  $("play").disabled=false; $("play").textContent="Cash Out";
  const tick=()=>{m=Math.round((1+((performance.now()-start)/1000)*0.35)*100)/100; status(`Multiplier ${m.toFixed(2)}x — cash out before ${info.crash_at.toFixed(2)}x`); if(m<info.crash_at){requestAnimationFrame(tick)}else{status("Crashed — bet lost.");$("play").textContent="Play";$("play").onclick=startGame}};requestAnimationFrame(tick);
  $("play").onclick=async()=>{try{const j=await json("/games/crash/cashout",{multiplier:m});status(j.ok?`Cashed out ${j.payout.toFixed(2)} KES`:"Crashed.");$("play").textContent="Play";$("play").onclick=startGame}catch(e){status(e.message)}};
}
async function startGame(){
 try{
  $("play").disabled=true;
  let j;
  if(game==="crash"){j=await json("/games/crash/start",{bet:bet()});crashLoop(j);return}
  if(game==="mines"){j=await json("/games/mines/start",{bet:bet(),bombs:+$("bombs").value});board(`<div class="lz-board">${Array.from({length:25},(_,i)=>`<button class="lz-cell" data-cell="${i}">?</button>`).join("")}</div>`);document.querySelectorAll("[data-cell]").forEach(b=>b.onclick=()=>openMine(+b.dataset.cell));status("Choose a tile.");$("play").hidden=true;$("claim").hidden=false;$("claim").onclick=claim;return}
  if(game==="tower"){j=await json("/games/tower/start",{bet:bet(),bombs:+$("bombs").value});renderTower(j.row);status("Choose a slot.");$("play").hidden=true;$("claim").hidden=false;$("claim").onclick=claim;return}
  if(game==="dice"){j=await json("/games/dice/play",{bet:bet(),target:+$("target").value,mode:$("mode").value});status(`Roll ${j.roll.toFixed(2)} — ${j.won?"WIN":"LOSS"} — payout ${j.payout.toFixed(2)} KES`);$("play").disabled=false;return}
  if(game==="battle"){j=await json("/games/battle/play",{bet:bet()});status(`You ${j.player} vs House ${j.house} — ${j.won?"WIN":"LOSS"} — payout ${j.payout.toFixed(2)} KES`);$("play").disabled=false;return}
  if(game==="wheel"){j=await json("/games/wheel/play",{bet:bet(),color:$("color").value});status(`Wheel: ${j.result} — ${j.won?"WIN":"LOSS"} — payout ${j.payout.toFixed(2)} KES`);$("play").disabled=false;return}
  if(game==="hilo"){j=await json("/games/hilo/start",{bet:bet()});renderHilo(j.card,j.claim);return}
 }catch(e){status(e.message);$("play").disabled=false}
}
async function openMine(cell){try{const j=await json("/games/mines/open",{cell});const b=document.querySelector(`[data-cell="${cell}"]`);b.textContent=j.hit?"💣":"💎";b.classList.add(j.hit?"mine":"open");status(j.hit?"Mine hit — round lost.":`Safe. Claim: ${j.claim.toFixed(2)} KES`);if(j.hit){$("claim").hidden=true;$("play").hidden=false;$("play").disabled=false;$("play").textContent="Play";$("play").onclick=startGame}}catch(e){status(e.message)}}
async function claim(){try{const j=await json(`/games/${game}/claim`);status(`Claimed ${j.payout.toFixed(2)} KES`);$("claim").hidden=true;$("play").hidden=false;$("play").disabled=false;$("play").textContent="Play";$("play").onclick=startGame}catch(e){status(e.message)}}
function renderTower(row){board(`<div class="lz-board">${[0,1,2,3,4].map(i=>`<button class="lz-cell" data-slot="${i}">Pick</button>`).join("")}</div><div class="lz-result">Level ${row}/10</div>`);document.querySelectorAll("[data-slot]").forEach(b=>b.onclick=()=>towerPick(+b.dataset.slot))}
async function towerPick(slot){try{const j=await json("/games/tower/next",{slot});status(j.hit?"Bomb! Round lost.":`Safe — level ${j.row}/10. Claim: ${(j.claim||j.payout||0).toFixed(2)} KES`);if(j.hit||j.row>=10){$("claim").hidden=true;$("play").hidden=false;$("play").disabled=false;$("play").textContent="Play";$("play").onclick=startGame}else renderTower(j.row)}catch(e){status(e.message)}}
function renderHilo(card,claim){board(`<div class="lz-result">Current card: ${card.value} (${["♠","♥","♦","♣"][card.suit]})</div><button id="higher">Higher</button><button id="lower">Lower</button><button id="equal">Equal</button>`);["higher","lower","equal"].forEach(p=>$(p).onclick=()=>hiloFlip(p));$("play").hidden=true;$("claim").hidden=false;$("claim").onclick=claim}
async function hiloFlip(p){try{const j=await json("/games/hilo/flip",{prediction:p});status(`Next: ${j.next.value} — ${j.outcome} — ${j.won?"correct":"wrong"}`);if(!j.won){$("claim").hidden=true;$("play").hidden=false;$("play").disabled=false;$("play").textContent="Play";$("play").onclick=startGame}else renderHilo(j.next,j.claim)}catch(e){status(e.message)}}
$("play").onclick=startGame;
$("claim").hidden=true;
const css=document.createElement("link");css.rel="stylesheet";css.href="/static/games/luck2x/games.css";document.head.appendChild(css);
})();