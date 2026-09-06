/**
 * 解析 B 站下载文件的任务/文件名，用于和下载队列一致地展示标题。
 * 兼容两种命名：
 *   旧格式：{系列名}..._{BV号}{_pN}.mp4
 *   新格式：{BV号}{_pN}_{系列名}.mp4
 * 返回 mainTitle（P167 · 分P名）与 subTitle（系列名）。
 */
export interface BiliNameInfo {
  isBili: boolean
  bv: string
  pageNo: number | null
  /** 系列名（可能被文件名截断） */
  series: string
  /** 分P名（文件名里带出来时才有） */
  part: string | null
  /** 主标题：多P 显示 "P167 · 分P名"，否则原始去扩展名文件名 */
  mainTitle: string
  /** 副标题：多P 时为系列名，否则 null */
  subTitle: string | null
}

const EXT = /\.(mp4|avi|mov|mkv|webm|flv|m4v)$/i

export function parseBiliTaskName(filename: string): BiliNameInfo {
  const base = (filename || '').replace(EXT, '')
  const none: BiliNameInfo = {
    isBili: false,
    bv: '',
    pageNo: null,
    series: base,
    part: null,
    mainTitle: base,
    subTitle: null,
  }
  if (!base) return none

  // 新格式：BV..._pN_系列名[ P N 分P名]
  let m = base.match(/^(BV[0-9A-Za-z]+)(?:_p(\d+))?_(.+)$/)
  if (m) {
    const pageNo = m[2] ? parseInt(m[2], 10) : null
    const rest = m[3]
    let series = rest
    let part: string | null = null
    const pm = pageNo ? rest.match(new RegExp(`^(.*?)[\\s_]*P${pageNo}[\\s_]+(.+)$`)) : null
    if (pm) {
      series = pm[1].replace(/[\s_]+$/, '').trim()
      part = pm[2].trim()
    }
    return {
      isBili: true,
      bv: m[1],
      pageNo,
      series,
      part,
      mainTitle: pageNo ? `P${pageNo}${part ? ' · ' + part : ''}` : m[1],
      subTitle: series || null,
    }
  }

  // 旧格式：系列名_BV..._pN
  m = base.match(/^(.+?)[\s_]*((?:BV[0-9A-Za-z]+))(?:_p(\d+))?$/)
  if (m) {
    const pageNo = m[3] ? parseInt(m[3], 10) : null
    let series = m[1].replace(/_+$/, '').trim()
    let part: string | null = null
    // 系列名尾部可能带 " P167 分P名"
    const partMatch = series.match(/\sP(\d+)\s+(.+)$/)
    if (partMatch && pageNo && parseInt(partMatch[1], 10) === pageNo) {
      part = partMatch[2]
      series = series.slice(0, partMatch.index).trim()
    }
    return {
      isBili: true,
      bv: m[2],
      pageNo,
      series,
      part,
      mainTitle: pageNo
        ? `P${pageNo}${part ? ' · ' + part : ''}`
        : series || base,
      subTitle: pageNo ? series || null : null,
    }
  }

  return none
}
