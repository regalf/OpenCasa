const BASE = '/api/v1'

let token = localStorage.getItem('token')

export function setToken(t) {
  token = t
  if (t) localStorage.setItem('token', t)
  else localStorage.removeItem('token')
}

export function getToken() {
  return token
}

async function request(method, path, body) {
  const headers = { 'Content-Type': 'application/json' }
  if (token) headers['Authorization'] = 'Bearer ' + token
  const opts = { method, headers }
  if (body) opts.body = JSON.stringify(body)
  const res = await fetch(BASE + path, opts)
  if (res.status === 401) {
    setToken(null)
    window.dispatchEvent(new CustomEvent('auth:logout'))
    throw new Error('Unauthorized')
  }
  return res.json()
}

export const api = {
  login: (user, pass) =>
    fetch(BASE + '/auth/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username: user, password: pass }),
    }).then(r => r.json()),

  getDisk: () => request('GET', '/disks'),
  getStorage: () => request('GET', '/storage'),
  getStats: () => request('GET', '/system/stats'),
  getInfo: () => request('GET', '/system/info'),

  listFiles: (path) => request('GET', '/files?path=' + encodeURIComponent(path)),
  readFile: (path) => request('GET', '/files/read?path=' + encodeURIComponent(path)),
  writeFile: (path, content) => request('POST', '/files/write', { path, content }),
  deleteFile: (path) => request('POST', '/files/delete', { path }),
  renameFile: (oldPath, newPath) => request('POST', '/files/rename', { old_path: oldPath, new_path: newPath }),
  mkdir: (path) => request('POST', '/files/mkdir', { path }),
  createUploadUrl: () => BASE + '/files/upload',

  getApps: () => request('GET', '/apps'),
  registerApp: (app) => request('POST', '/apps/register', app),
  startApp: (id) => request('POST', '/apps/start', { id }),
  stopApp: (id) => request('POST', '/apps/stop', { id }),
  appStatus: (id) => request('GET', '/apps/status?id=' + encodeURIComponent(id)),

  getNotifications: () => request('GET', '/notifications'),
  sendNotification: (appId, title, msg, severity) =>
    request('POST', '/notify', { app_id: appId, title, message: msg, severity }),
}
