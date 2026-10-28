const desktop = '__TAURI_INTERNALS__' in window;
const base = desktop ? 'http://127.0.0.1:4319' : '';
export async function api<T>(path:string, body?:unknown):Promise<T> {
  const response = await fetch(base+'/api'+path, body === undefined ? {} : {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const text = await response.text();
  let result;
  try { result = JSON.parse(text); } catch { throw new Error('The local service is unavailable. Check that the Python API is running on port 4319, then retry.'); }
  if (!response.ok) throw new Error(result.error || 'The local service could not complete this request.');
  return result;
}
export function download(filename:string, content:string, type='text/markdown') {
  const url=URL.createObjectURL(new Blob([content],{type}));
  const a=document.createElement('a'); a.href=url; a.download=filename; a.click(); setTimeout(()=>URL.revokeObjectURL(url),1000);
}
