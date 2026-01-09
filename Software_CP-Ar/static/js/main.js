const ctx = document.getElementById('grafico').getContext('2d');
const config = {
  type: 'line',
  data: { labels: [], datasets: [{ label:'Aceleración Z (m/s²)', data:[], borderColor:'#6b63bf', fill:false, tension:0.1 }] },
  options: {
    responsive:true, animation:false,
    scales:{ y:{ min:-20,max:0, title:{display:true,text:'m/s²'} },
             x:{ min:0, max:1000, title:{display:true,text:'Índice de muestra'} } }
  }
};
const grafico = new Chart(ctx, config);

async function actualizarDatos(){
  const r = await fetch('/datos'); const j = await r.json();
  config.data.labels = j.indices;
  config.data.datasets[0].data = j.valores;
  grafico.update();
}
setInterval(actualizarDatos, 100);
async function actualizarStats(){
  const r = await fetch('/stats'); const j = await r.json();
  document.getElementById('n_comp').textContent = j.n_comp;
  document.getElementById('cpm').textContent    = j.cpm.toFixed(1);
  document.getElementById('metric-cpm').textContent = j.cpm.toFixed(0);
  document.getElementById('prof_cm').textContent = j.prof_cm.toFixed(1);
  document.getElementById('metric-prof').textContent = j.prof_cm.toFixed(1);

}
setInterval(actualizarStats, 300);

async function actualizarTimer() {
    try {
        const r = await fetch('/api/device-info'); 
        const j = await r.json();

        const sessionDuration = j.session.duration; 
        const timerElement = document.getElementById('metric-t_rcp');
        
 
        if (timerElement) {
            if (sessionDuration !== '—') {
                timerElement.textContent = sessionDuration; 
            } else {
                timerElement.textContent = '00:00';        
            }
        }
        

    } catch (e) {
        console.error('Error al actualizar el timer:', e);
    }
}
setInterval(actualizarTimer, 500);



const reportBtn    = document.getElementById('btn-ver-reporte'); 
const reportTabBtn = document.getElementById('tab-reporte-tab'); 
const reportFrame  = document.getElementById('report-frame');    

function reloadReportFrame(){
  if (!reportFrame) return;
  if (reportFrame.contentWindow) reportFrame.contentWindow.location.reload();
  else reportFrame.src = reportFrame.src;
}

function showReportTabAndReload(){
  if (typeof bootstrap !== 'undefined' && reportTabBtn) {
    const tab = new bootstrap.Tab(reportTabBtn);
    tab.show();
  }
  reloadReportFrame();
}


function toggleReporte(enable){
  if (!reportBtn) return;
  reportBtn.disabled = !enable;
  reportBtn.onclick = enable
    ? () => showReportTabAndReload()  
    : null;
}

async function iniciar(){
  const comentario = document.getElementById("comentario").value;
  await fetch('/start', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({ comentario })
  });
  
  
  toggleDescarga(false);
  toggleReporte(false);
}
async function detener(){
  const stopBtn = document.querySelector('.btn.btn-soft[onclick="detener()"]') 
                  || document.getElementById('btn-stop'); // por si luego le ponés id
  try {
    if (stopBtn) { stopBtn.disabled = true; stopBtn.textContent = 'Deteniendo...'; }


    const res = await fetch('/stop', { method: 'POST' });
    const ct  = res.headers.get('content-type') || '';
    const data = ct.includes('application/json') ? await res.json() : null;

    toggleDescarga(true);

    const success = res.ok && (!data || data.ok === true);
    if (!success) {
      const msg = (data && (data.error || data.message)) || res.statusText;
      alert('No se pudo generar el reporte.\n' + msg);
      return;
    }

    toggleReporte(true);   

  } catch (err) {
    alert('Error de red al detener: ' + err.message);
  } finally {
    if (stopBtn) { stopBtn.disabled = false; stopBtn.textContent = '⏹ Stop'; }
  }
}
function toggleDescarga(enable){
  const btn = document.getElementById('btn-descargar');
  if(enable){ btn.classList.remove('disabled'); }
  else{ btn.classList.add('disabled'); }
}
