#!/usr/bin/env node
/**
 * format_email_brief.js — Read email-monitor JSON output and format as readable brief
 * Usage: node format_email_brief.js <brief.json>
 */
const fs = require('fs');

const file = process.argv[2];
if (!file) { console.log('Usage: node format_email_brief.js <brief.json>'); process.exit(1); }
if (!fs.existsSync(file)) { console.log('File not found:', file); process.exit(1); }

const data = JSON.parse(fs.readFileSync(file, 'utf-8'));
const now = new Date().toLocaleString('zh-CN', { timeZone: 'Asia/Shanghai' });

let lines = [];
lines.push('📬 邮件简报 \u2014 ' + now);
lines.push('\u2501'.repeat(32));

let totalNew = 0;
for (const acct of data.accounts) {
    const label = acct.label || acct.name || '未知';
    const count = acct.count || 0;
    totalNew += count;

    let status = '\u3010' + label + '\u3011';
    if (acct.error) {
        status += ' \u26a0\ufe0f ' + acct.error;
    } else if (count === 0) {
        status += ' \u2705 \u65e0\u65b0\u90ae\u4ef6';
    } else {
        status += ' \u2014 ' + count + ' \u5c01\u65b0\u90ae\u4ef6 / \u5171 ' + acct.mailboxTotal + ' \u5c01';
    }
    lines.push(status);

    if (count > 0) {
        const acctEmails = data.emails.filter(function(e) { return e.account === acct.name; });
        for (var i = 0; i < Math.min(count, 8); i++) {
            var email = acctEmails[i];
            if (!email) continue;
            var d = new Date(email.date);
            var dateStr = d.toLocaleDateString('zh-CN', { timeZone: 'Asia/Shanghai' });
            var fromName = email.from ? email.from.split('<')[0].trim().replace(/"/g, '') || email.from.split('<')[1]?.replace('>','') || email.from : '(?)';
            var preview = email.preview
                ? email.preview.replace(/\n/g, ' ').replace(/\s+/g, ' ').substring(0, 80) + (email.preview.length > 80 ? '...' : '')
                : '(\u65e0\u5185\u5bb9)';
            lines.push('  \u2022 [' + dateStr + '] ' + fromName);
            lines.push('    ' + email.subject);
            lines.push('    ' + preview);
        }
        if (count > 8) {
            lines.push('    ... \u8fd8\u6709 ' + (count - 8) + ' \u5c01');
        }
    }
}

lines.push('\u2501'.repeat(32));
lines.push('\u5171\u8ba1 ' + totalNew + ' \u5c01\u65b0\u90ae\u4ef6');
lines.push('\u2728 \u56de\u590d\u300c\u67e5\u770b <\u7f16\u53f7>\u300d\u67e5\u770b\u5b8c\u6574\u90ae\u4ef6');

console.log(lines.join('\n'));
