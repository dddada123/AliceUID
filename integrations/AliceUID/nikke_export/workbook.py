"""Generate a macro-free workbook with cached results and scalar filter formulas."""
from __future__ import annotations

from io import BytesIO
import math
import unicodedata

from .model import ExportData, ExportError

MAX_FILE_BYTES = 12 * 1024 * 1024
DATA_FIRST = 6  # zero-based; row 6 is the Excel table header
VIEW_FIRST = 5
BLOCK_ROWS = 15


def build_workbook(data: ExportData) -> bytes:
    try:
        import xlsxwriter
        from xlsxwriter.utility import xl_col_to_name as colname
    except ImportError as exc:
        raise ExportError('缺少 Excel 导出组件 XlsxWriter，请管理员安装插件依赖并重启 Core。') from exc
    stream = BytesIO()
    book = xlsxwriter.Workbook(stream, {'in_memory': True, 'strings_to_formulas': False,
                                      'strings_to_urls': False, 'strings_to_numbers': False})
    book.set_properties({'title': 'NIKKE练度表', 'subject': '本人本地练度缓存', 'author': 'AliceUID',
                         'comments': '由 AliceUID 1.0.18 导出；不含登录凭据。', 'created': data.exported_at.replace(tzinfo=None)})
    book.set_calc_mode('auto')
    overview = book.add_worksheet('练度总览')
    detail = book.add_worksheet('数据明细')
    navy, blue, pale, gray = '#16324F', '#1769B0', '#EDF3F9', '#61758A'
    base = {'font_name': '微软雅黑', 'font_size': 10, 'font_color': '#243B53', 'valign': 'vcenter'}
    def fmt(**kwargs):
        return book.add_format(dict(base, **kwargs))
    formats = dict(
        title=fmt(font_size=16, bold=True, font_color='white', bg_color=navy),
        subtitle=fmt(font_size=10, font_color=gray),
        label=fmt(bold=True, font_color=navy, bg_color=pale),
        input=fmt(bold=True, font_color=blue, bg_color='#E5F2FF', border=1, border_color='#93B8DA', align='center'),
        header=fmt(bold=True, font_color='white', bg_color=navy, text_wrap=True),
        role=fmt(bold=True, font_size=12, font_color='white', bg_color=navy, text_wrap=True),
        meta=fmt(font_size=9, font_color=gray, bg_color=pale, text_wrap=True),
        power=fmt(bold=True, font_color='#75C7FF', bg_color=navy, align='right'),
        gear=fmt(bold=True, bg_color=pale, text_wrap=True, align='center', border=1, border_color='#DBE5EE'),
        text=fmt(text_wrap=True),
        value=fmt(bold=True, num_format='0.00%', align='right'),
        tier=fmt(font_size=9, font_color=gray, num_format='0"阶"', align='center'),
        summary=fmt(font_size=10, text_wrap=True, valign='top', bg_color='#F5F8FC', indent=1),
        integer=fmt(num_format='#,##0'),
        number=fmt(num_format='0.00'),
        percent=fmt(num_format='0.00%'),
        blank=fmt(font_color='white', bg_color='white', border=1, border_color='white'),
        max_name=fmt(bg_color='#101923', font_color='white'),
        max_value=fmt(bg_color='#101923', font_color='#81C8FF', bold=True),
        rare=fmt(font_color=blue, bold=True),
        muted=fmt(font_color='#8996A5'),
    )
    # Alternate individual data rows; merged equipment/summary blocks keep their fills.
    row_styles = {
        'text': dict(text_wrap=True),
        'value': dict(bold=True, num_format='0.00%', align='right'),
        'tier': dict(font_size=9, font_color=gray, num_format='0"阶"', align='center'),
        'integer': dict(num_format='#,##0'),
        'number': dict(num_format='0.00'),
        'percent': dict(num_format='0.00%'),
    }
    row_formats = [{key: fmt(bg_color=color, **props) for key, props in row_styles.items()}
                   for color in ('#F0F2F5', '#FFFFFF')]
    formats['notice'] = fmt(font_size=9, font_color=gray, text_wrap=True)
    columns = {column.key: index for index, column in enumerate(data.columns)}
    n = len(data.rows)
    last = DATA_FIRST+n
    def source(key):
        c = colname(columns[key])
        return f"'数据明细'!${c}${DATA_FIRST+1}:${c}${last}"
    def write_value(sheet, r, c, value, cell_format=None):
        if isinstance(value, (int, float)) and not isinstance(value, bool):
            if not math.isfinite(value):
                raise ExportError('缓存包含无效数值，已停止导出。')
            sheet.write_number(r, c, value, cell_format)
        else:
            sheet.write_string(r, c, str(value if value is not None else '未知'), cell_format)
    def merge_text(sheet, r1, c1, r2, c2, value, cell_format):
        sheet.merge_range(r1,c1,r2,c2,'',cell_format)
        sheet.write_string(r1,c1,value,cell_format)
    identity = f'{data.commander["name"]}    {data.commander["region"]}    UID {data.commander["uid"]}    指挥官 Lv.{data.commander["level"] or "未知"}'
    timing = f'缓存最近更新 {data.cache_time:%Y-%m-%d %H:%M}    导出 {data.exported_at:%Y-%m-%d %H:%M}    北京时间'
    for sheet in (overview, detail):
        sheet.hide_gridlines(2)
        sheet.set_default_row(24)
        sheet.set_tab_color(blue if sheet == overview else '#8AA4BD')
        merge_text(sheet,0,0,0,10,'[AliceUID]  NIKKE练度表',formats['title'])
        sheet.set_row(0,28)
        identity_end = 5 if sheet == overview else 10
        merge_text(sheet,1,0,1,identity_end,identity,formats['subtitle'])
        merge_text(sheet,2,0,2,identity_end,timing,formats['subtitle'])
    detail.freeze_panes(DATA_FIRST,2)
    detail.set_zoom(90)
    merge_text(detail,3,0,3,10,'每名妮姬一行。表头可多选筛选、数值排序；百分比列保存为数字。未知、未提供不计作0。',formats['subtitle'])
    headers = [{'header': column.label, 'header_format': formats['header']} for column in data.columns]
    detail.add_table(DATA_FIRST-1,0,last-1,len(data.columns)-1,{'name':'NikkeDetails','columns':headers,'style':'Table Style Medium 2'})
    detail.set_row(DATA_FIRST-1,42)
    for index, column in enumerate(data.columns):
        width = 22 if column.key == 'name' else 20 if column.kind == 'text' else 16
        detail.set_column(index,index,width,formats.get(column.kind), {'hidden':True} if column.hidden else {})
    matchcol, rankcol = colname(columns['_match']), colname(columns['_rank'])
    positioncol = colname(columns['_position'])
    burstcol, rolecol, companycol, elementcol = (colname(columns[k]) for k in ('burst','role','company','element'))
    for i,row in enumerate(data.rows):
        r = DATA_FIRST+i
        er = r+1
        for c,column in enumerate(data.columns):
            if column.key in ('_match','_rank','_position'):
                continue
            value = row.get(column.key,'')
            kind = column.kind
            if kind == 'affix':
                kind = 'percent' if row[column.key.replace('_value','_unit')] == 'Percent' else 'number'
            write_value(detail,r,c,value,row_formats[i % 2].get(kind,row_formats[i % 2]['text']))
        stage = f'INDEX(${burstcol}${DATA_FIRST+1}:${burstcol}${last},ROW()-{DATA_FIRST})'
        role = f'INDEX(${rolecol}${DATA_FIRST+1}:${rolecol}${last},ROW()-{DATA_FIRST})'
        company = f'INDEX(${companycol}${DATA_FIRST+1}:${companycol}${last},ROW()-{DATA_FIRST})'
        element = f'INDEX(${elementcol}${DATA_FIRST+1}:${elementcol}${last},ROW()-{DATA_FIRST})'
        condition = (f'AND(OR(练度总览!$H$2="全部",{stage}=练度总览!$H$2,'
                     f'AND({stage}="全阶段",OR(练度总览!$H$2="Ⅰ",练度总览!$H$2="Ⅱ",练度总览!$H$2="Ⅲ"))),'
                     f'OR(练度总览!$H$4="全部",{role}=练度总览!$H$4),'
                     f'OR(练度总览!$H$3="全部",{company}=练度总览!$H$3),'
                     f'OR(练度总览!$H$5="全部",{element}=练度总览!$H$5))')
        detail.write_formula(r,columns['_match'],f'=IF({condition},1,0)',None,1)
        current_match = f'INDEX(${matchcol}${DATA_FIRST+1}:${matchcol}${last},ROW()-{DATA_FIRST})'
        detail.write_formula(r,columns['_position'],'=ROW()',None,er)
        detail.write_formula(r,columns['_rank'],f'=IF({current_match}=1,COUNTIFS(${positioncol}${DATA_FIRST+1}:${positioncol}${last},"<="&ROW(),${matchcol}${DATA_FIRST+1}:${matchcol}${last},1),0)',None,i+1)
        for slot in ('head','torso','arm','leg'):
            for num in (1,2,3):
                key=f'{slot}_{num}'
                nc,vc,lc=(columns[key+'_'+suffix] for suffix in ('name','value','level'))
                levelcell=f'${colname(lc)}{er}'
                detail.conditional_format(r,nc,r,nc,{'type':'formula','criteria':f'={levelcell}=15','format':formats['max_name']})
                detail.conditional_format(r,vc,r,lc,{'type':'formula','criteria':f'={levelcell}=15','format':formats['max_value'],'stop_if_true':True})
                detail.conditional_format(r,vc,r,vc,{'type':'formula','criteria':f'=AND(ISNUMBER({levelcell}),{levelcell}>=12,{levelcell}<15)','format':formats['rare']})
    widths = [16,22,12,7,34,2.5,16,22,12,7,34]
    for c,width in enumerate(widths):
        overview.set_column(c,c,width)
    overview.set_column(11,14,10,None,{'hidden':True})
    overview.set_zoom(85)
    overview.freeze_panes(VIEW_FIRST,0)
    overview.set_row(0,26)
    overview.set_row(1,28)
    for r in range(2,5):
        overview.set_row(r,20)
    for r,label in ((1,'爆裂阶段'),(2,'企业'),(3,'角色定位'),(4,'角色属性')):
        overview.write_string(r,6,label,formats['label'])
        overview.write_string(r,7,'全部',formats['input'])
    dropdowns=[('H2',['全部','Ⅰ','Ⅱ','Ⅲ','全阶段','未知']),('H4',['全部','火力型','防御型','辅助型','未知']),
               ('H5',['全部','燃烧','水冷','铁甲','电击','风压','未知'])]
    companies = ['全部']+sorted({str(row['company']) for row in data.rows})
    for i,value in enumerate(companies):
        overview.write_string(i,14,value)
    book.define_name('CompanyChoices',f"练度总览!$O$1:$O${len(companies)}")
    for cell,choices in dropdowns:
        overview.data_validation(cell,{'validate':'list','source':choices,'error_title':'请选择列表中的条件',
                                       'error_message':'选择“全部”可取消此条件。','error_type':'stop'})
    overview.data_validation('H3',{'validate':'list','source':'=CompanyChoices','error_type':'stop'})
    overview.merge_range('I2:K2','全阶段角色同时匹配Ⅰ、Ⅱ、Ⅲ；\n最新全量数据请先刷新面板。',formats['notice'])
    overview.merge_range('I3:K3',f'已导出 {n} 名',formats['subtitle'])
    overview.merge_range('I4:K4','',formats['label'])
    overview.write_formula('I4',f'="符合条件 "&COUNTIF({source("_match")},1)&" 名"',formats['label'],f'符合条件 {n} 名')
    overview.merge_range('A4:F4','12～14阶：蓝色数字    15阶：黑底亮蓝',formats['subtitle'])
    overview.merge_range('I5:K5','',formats['subtitle'])
    overview.write_formula('I5',f'=IF(COUNTIF({source("_match")},1)=0,"没有符合条件的妮姬","")',formats['subtitle'],'')
    for i in range(n):
        overview.write_formula(i,12,f'=IFERROR(MATCH({i+1},{source("_rank")},0),0)',None,i+1)
    def indexed(rownum, col, key, i, cell_format, merge=None):
        idx=f'$M${i+1}'
        formula=f'=IF({idx}=0,"",INDEX({source(key)},{idx}))'
        if merge:
            overview.merge_range(rownum,col,merge[0],merge[1],'',cell_format)
        overview.write_formula(rownum,col,formula,cell_format,data.rows[i].get(key,''))
    def wrapped_lines(text, width):
        return sum(max(1, math.ceil(sum(2 if unicodedata.east_asian_width(c) in ('W','F') else 1 for c in line)/width))
                   for line in str(text).split('\n'))
    summary_lines = max(wrapped_lines(row['_summary'],32) for row in data.rows)
    affix_lines = max(wrapped_lines(row.get(f'{slot}_{num}_{part}',''), width)
                      for row in data.rows for slot in ('head','torso','arm','leg')
                      for num in (1,2,3) for part,width in (('name',22),('value',12)))
    body_height = max(25, math.ceil((summary_lines*15+12)/12),affix_lines*14)
    for i in range(n):
        top = VIEW_FIRST + (i//2)*BLOCK_ROWS
        left = 0 if i%2 == 0 else 6
        idx=f'$M${i+1}'
        indexed(top,left,'_title',i,formats['role'],merge=(top,left+3))
        indexed(top,left+4,'_power',i,formats['power'])
        indexed(top+1,left,'_meta',i,formats['meta'],merge=(top+1,left+3))
        overview.write_formula(top+1,left+4,f'=IF({idx}=0,"","练度 / 同类词条汇总")',formats['label'],'练度 / 同类词条汇总')
        overview.set_row(top,38)
        overview.set_row(top+1,30)
        for k in range(12):
            overview.set_row(top+2+k,body_height)
        indexed(top+2,left+4,'_summary',i,formats['summary'],merge=(top+13,left+4))
        overview.conditional_format(top,left,top+13,left+4,{'type':'formula','criteria':f'={idx}=0','format':formats['blank'],'stop_if_true':True})
        for s,slot in enumerate(('head','torso','arm','leg')):
            gearrow = top+2+s*3
            indexed(gearrow,left,'_'+slot,i,formats['gear'],merge=(gearrow+2,left))
            for num in (1,2,3):
                r=gearrow+num-1
                key=f'{slot}_{num}'
                for offset,suffix,style in ((1,'name','text'),(2,'value','value'),(3,'level','tier')):
                    indexed(r,left+offset,key+'_'+suffix,i,row_formats[(r-top-2) % 2][style])
                levelcell=f'${colname(left+3)}{r+1}'
                overview.conditional_format(r,left+1,r,left+1,{'type':'formula','criteria':f'={levelcell}=15','format':formats['max_name']})
                overview.conditional_format(r,left+2,r,left+3,{'type':'formula','criteria':f'={levelcell}=15','format':formats['max_value']})
                overview.conditional_format(r,left+2,r,left+2,{'type':'formula','criteria':f'=AND(ISNUMBER({levelcell}),{levelcell}>=12,{levelcell}<15)','format':formats['rare']})
                overview.conditional_format(r,left+2,r,left+2,{'type':'formula','criteria':f'=IF({idx}=0,FALSE,INDEX({source(key+"_unit")},{idx})<>"Percent")','format':formats['number']})
        overview.set_row(top+14,12)
    overview.set_landscape()
    overview.set_paper(9)
    overview.fit_to_pages(1,0)
    overview.repeat_rows(0,VIEW_FIRST-1)
    overview.set_margins(0.25,0.25,0.35,0.35)
    overview.print_area(0,0,VIEW_FIRST+math.ceil(n/2)*BLOCK_ROWS-2,10)
    overview.set_header('&CAliceUID · NIKKE练度表')
    overview.set_footer('&L'+data.exported_at.strftime('%Y-%m-%d %H:%M 北京时间')+'&R第 &P 页 / &N 页')
    overview.activate()
    book.close()
    result=stream.getvalue()
    if len(result)>MAX_FILE_BYTES:
        raise ExportError('导出文件超出12MB上限，已停止发送，请联系管理员检查。')
    return result
