// Cấu hình Metro (spec fe-pose-logic §2.2, §6 ý 2).
// Bảng luật tư thế nằm ở `../shared/constants/pose-rules.json`, ngoài thư mục `frontend/`, để dùng chung với
// worker video Python. Metro mặc định chỉ theo dõi thư mục dự án, nên phải thêm `../shared` vào `watchFolders`
// thì mới bundle được file đó.
const { getDefaultConfig } = require('expo/metro-config');
const path = require('path');

const config = getDefaultConfig(__dirname);

config.watchFolders = [...(config.watchFolders ?? []), path.resolve(__dirname, '../shared')];

module.exports = config;
