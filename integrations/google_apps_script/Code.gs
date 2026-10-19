/* One central writer for all desktops. Set Script Properties before setup(). */
const BUSINESS_HEADERS = ['STT', 'TÊN MAP', 'TỌA ĐỘ X', 'TỌA ĐỘ Y', 'ẢNH MINH CHỨNG', 'MÔ TẢ / GHI CHÚ', 'TRẠNG THÁI'];
const META_HEADERS = ['incident_id', 'revision', 'observed_at', 'confidence'];

function settings_() {
  const p = PropertiesService.getScriptProperties();
  const spreadsheetId = p.getProperty('SPREADSHEET_ID');
  const folderId = p.getProperty('EVIDENCE_FOLDER_ID');
  const token = p.getProperty('SYNC_TOKEN');
  const gidText = p.getProperty('SHEET_GID');
  if (!spreadsheetId || !folderId || !token || token.length < 32 || gidText === null) {
    throw new Error('CONFIG: Thiếu Script Properties hoặc token ngắn hơn 32 ký tự.');
  }
  const gid = Number(gidText);
  const sheet = SpreadsheetApp.openById(spreadsheetId).getSheets().find(s => s.getSheetId() === gid);
  if (!sheet) throw new Error('CONFIG: Không tìm thấy tab theo SHEET_GID.');
  return {spreadsheetId, folderId, token, gid, sheet};
}

/* Run explicitly in the editor once, using an account allowed to write Sheet/Drive. */
function setup() {
  const c = settings_();
  const lock = LockService.getScriptLock();
  lock.waitLock(10000);
  try {
    const current = c.sheet.getRange(1, 1, 1, 11).getDisplayValues()[0];
    const expected = BUSINESS_HEADERS.concat(META_HEADERS);
    current.forEach((value, i) => {
      if (value && value.trim() !== expected[i]) throw new Error('CONFIG: Tiêu đề cột ' + (i+1) + ' chưa khớp. Không sửa dữ liệu hiện có.');
    });
    c.sheet.getRange(1, 1, 1, 11).setValues([expected]);
    DriveApp.getFolderById(c.folderId).getName();
    SpreadsheetApp.flush();
  } finally { lock.releaseLock(); }
}

function headers_(c) {
  const values = c.sheet.getRange(1, 1, 1, 11).getDisplayValues()[0];
  if (JSON.stringify(values) !== JSON.stringify(BUSINESS_HEADERS.concat(META_HEADERS))) {
    throw new Error('CONFIG: Tiêu đề thay đổi; cần đối soát trước khi ghi.');
  }
}

function rowFor_(c, id) {
  const count = c.sheet.getLastRow() - 1;
  if (count <= 0) return 0;
  const matches = c.sheet.getRange(2, 8, count, 1).createTextFinder(id).matchEntireCell(true).useRegularExpression(false).findAll();
  if (matches.length > 1) throw new Error('CONFIG: Có nhiều dòng cùng incident_id; cần đối soát.');
  return matches.length ? matches[0].getRow() : 0;
}

function record_(c, row) {
  if (!row) return {found: false, revision: 0};
  const values = c.sheet.getRange(row, 1, 1, 11).getValues()[0];
  return {found: true, row, fields: values.slice(0, 7).map(String),
          revision: Number(values[8]), evidence_url: String(values[4])};
}

function handle_(c, request) {
  headers_(c);
  if (request.action === 'health') return {ready: true};
  const id = request.incident_id;
  if (typeof id !== 'string' || !/^[a-zA-Z0-9_-]{1,120}$/.test(id)) throw new Error('CONFIG: ID sự kiện không hợp lệ.');
  if (request.action === 'lookup') return record_(c, rowFor_(c, id));
  if (request.action === 'evidence') {
    const folder = DriveApp.getFolderById(c.folderId);
    if (typeof request.evidence_hash !== 'string' || !/^[a-f0-9]{64}$/.test(request.evidence_hash)) throw new Error('CONFIG: Thiếu dấu băm ảnh.');
    const name = id + '_' + request.evidence_hash + '.png';
    const files = folder.getFilesByName(name);
    if (files.hasNext()) return {url: files.next().getUrl(), evidence_hash: request.evidence_hash};
    if (typeof request.content !== 'string' || request.content.length > 6700000) throw new Error('CONFIG: Ảnh không hợp lệ hoặc vượt giới hạn.');
    const bytes = Utilities.base64Decode(request.content);
    if (bytes.length < 8 || ((bytes[0]+256)%256) !== 137 || bytes[1] !== 80 || bytes[2] !== 78 || bytes[3] !== 71) {
      throw new Error('CONFIG: Chỉ nhận ảnh PNG.');
    }
    const digest = Utilities.computeDigest(Utilities.DigestAlgorithm.SHA_256, bytes).map(b => ('0'+((b+256)%256).toString(16)).slice(-2)).join('');
    if (digest !== request.evidence_hash) throw new Error('CONFIG: Nội dung ảnh khác dấu băm.');
    const file = folder.createFile(Utilities.newBlob(bytes, 'image/png', name));
    // Inherit folder permissions; do not silently publish evidence to everyone.
    return {url: file.getUrl(), evidence_hash: request.evidence_hash};
  }
  if (request.action !== 'upsert') throw new Error('CONFIG: Hành động không hỗ trợ.');
  if (!Array.isArray(request.fields) || request.fields.length !== 7 ||
      !Number.isInteger(request.revision) || request.revision < 1) throw new Error('CONFIG: Thiếu trường dữ liệu.');
  const fields = request.fields.map(String);
  if (fields.some(value => value.length > 15000) || !fields[4].startsWith('https://drive.google.com/')) {
    throw new Error('CONFIG: Dữ liệu hoặc liên kết minh chứng không hợp lệ.');
  }
  let row = rowFor_(c, id);
  const old = record_(c, row);
  if (old.found && old.revision > request.revision) throw new Error('CONFIG: Phiên bản ghi cũ hơn Sheet.');
  if (old.found && old.revision === request.revision) {
    if (JSON.stringify(old.fields.slice(1)) !== JSON.stringify(fields.slice(1))) throw new Error('CONFIG: Cùng phiên bản nhưng khác nội dung.');
    return old;
  }
  if (row) fields[0] = old.fields[0];
  else {
    const numbers = c.sheet.getLastRow() > 1 ? c.sheet.getRange(2, 1, c.sheet.getLastRow()-1, 1).getValues().map(r => Number(r[0]) || 0) : [];
    fields[0] = String(numbers.reduce((maximum, value) => Math.max(maximum, value), 0) + 1);
    row = c.sheet.getLastRow() + 1;
  }
  const values = fields.concat([id, String(request.revision), String(request.timestamp || ''), String(request.confidence || '')]);
  // Rich text stores literal strings, including notes beginning with '='.
  const literal = values.map(value => SpreadsheetApp.newRichTextValue().setText(value).build());
  c.sheet.getRange(row, 1, 1, 11).setRichTextValues([literal]);
  SpreadsheetApp.flush();
  const readback = record_(c, row);
  if (readback.revision !== request.revision || JSON.stringify(readback.fields) !== JSON.stringify(fields)) {
    throw new Error('Đọc lại dữ liệu chưa khớp; cần đối soát.');
  }
  return readback;
}

function doPost(e) {
  let lock;
  let c;
  let result;
  try {
    const request = JSON.parse(e.postData.contents);
    c = settings_();
    if (request.token !== c.token) throw new Error('CONFIG: Xác thực không hợp lệ.');
    lock = LockService.getScriptLock();
    if (!lock.tryLock(5000)) throw new Error('Dịch vụ đang bận; thử lại sau.');
    result = {ok: true, ...handle_(c, request)};
  } catch (error) {
    const message = String(error.message || error);
    result = {ok: false, error: message, permanent: message.startsWith('CONFIG:')};
  } finally {
    if (lock && lock.hasLock()) lock.releaseLock();
  }
  // Never include credentials in responses or logs.
  if (c) { result.spreadsheet_id = c.spreadsheetId; result.gid = c.gid; }
  return ContentService.createTextOutput(JSON.stringify(result)).setMimeType(ContentService.MimeType.JSON);
}
