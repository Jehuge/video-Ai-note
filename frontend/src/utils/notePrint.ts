/** 文件名去掉扩展名，作为 PDF 文档标题和默认文件名。 */
export function noteTitle(filename?: string): string {
  const name = (filename || '笔记').replace(/\.[^/.]+$/, '')
  return name || '笔记'
}
