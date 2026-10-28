"""ModeShift Qt frontend preview. Does not alter the existing Tkinter entrypoint."""
from __future__ import annotations
import sys
from collections import deque
from PySide6.QtCore import Qt, QTimer, QPointF
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,
    QLabel,QPushButton,QFrame,QScrollArea,QStackedWidget,QMessageBox,
    QComboBox,QLineEdit,QCheckBox
)
from modeshift import Backend,TelemetrySampler,TW,POWER_SCHEMES, recommendations
import updater

STYLES={
    'Amber Night':('#090f1d','#121e30','#1a2a40','#ffb23f'),
    'Arctic Blue':('#091625','#13263b','#1a3852','#68b8ff'),
    'Graphite':('#111419','#1e232b','#292f38','#d7dae0'),
    'Forest':('#091810','#14281c','#1e3829','#60d79e'),
    'Crimson':('#160d16','#2a1825','#3c2334','#fb7291'),
}

def card():
    w=QFrame();w.setObjectName('card');return w

class Trends(QWidget):
    def __init__(self):
        super().__init__();self.setMinimumHeight(215);self.points=deque(maxlen=180)
    def add(self,info):
        self.points.append([info.get('cpu_percent'),info.get('ram_percent'),
                            max((g.get('utilization') or 0 for g in info.get('gpus') or []),default=None)])
        self.update()
    def paintEvent(self,event):
        p=QPainter(self);p.setRenderHint(QPainter.Antialiasing)
        rect=self.rect().adjusted(50,18,-17,-31)
        p.setPen(QColor('#617187'))
        for i in range(5):
            y=rect.bottom()-rect.height()*i/4
            p.drawLine(rect.left(),int(y),rect.right(),int(y))
            p.drawText(8,int(y)+4,f'{i*25}%')
        p.drawText(rect.left(),self.height()-9,'-3 min')
        p.drawText(rect.right()-25,self.height()-9,'Now')
        for index,color in enumerate(('#5eafff','#ffb23f','#47d9b4')):
            p.setPen(QPen(QColor(color),2.2))
            last=None
            for i,triplet in enumerate(self.points):
                val=triplet[index]
                if val is None:last=None;continue
                point=QPointF(rect.right()-(len(self.points)-1-i)*rect.width()/max(1,179),
                              rect.bottom()-max(0,min(100,val))*rect.height()/100)
                if last is not None:p.drawLine(last,point)
                last=point

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.backend=Backend();self.telemetry=TelemetrySampler()
        self.setWindowTitle('ModeShift — Qt Preview')
        self.resize(1330,850)
        self.root=QWidget();self.setCentralWidget(self.root)
        self.layout=QHBoxLayout(self.root);self.layout.setContentsMargins(0,0,0,0);self.layout.setSpacing(0)
        self.nav=QFrame();self.nav.setObjectName('sidebar');self.nav.setFixedWidth(220)
        nv=QVBoxLayout(self.nav);nv.setContentsMargins(16,26,16,20);nv.setSpacing(7)
        logo=QLabel('◈  MODESHIFT');logo.setObjectName('brand');nv.addWidget(logo)
        nv.addSpacing(26)
        self.pages=QStackedWidget()
        self.nav_buttons={}
        for name in ['Dashboard','Optimizations','Presets','Snapshots','Hardware','Settings']:
            button=QPushButton(name);button.setProperty('nav','true')
            button.clicked.connect(lambda _,n=name:self.show_page(n))
            nv.addWidget(button);self.nav_buttons[name]=button
        nv.addStretch();nv.addWidget(QLabel('LOCAL  •  NO SUBSCRIPTION'))
        self.layout.addWidget(self.nav)
        body=QFrame();bl=QVBoxLayout(body);bl.setContentsMargins(30,22,30,22);bl.setSpacing(18)
        top=QHBoxLayout();self.heading=QLabel('Dashboard');self.heading.setObjectName('heading');top.addWidget(self.heading)
        top.addStretch()
        self.update_btn=QPushButton('↻  Check updates');self.update_btn.clicked.connect(self.check_updates);top.addWidget(self.update_btn)
        bl.addLayout(top);bl.addWidget(self.pages,1);self.layout.addWidget(body,1)
        self.page_names=['Dashboard','Optimizations','Presets','Snapshots','Hardware','Settings']
        self.metric={}
        for name in self.page_names:
            builder=getattr(self,'build_'+name.lower())
            self.pages.addWidget(builder())
        self.theme=self.backend.data.get('theme','Amber Night')
        self.apply_theme(self.theme);self.show_page('Dashboard')
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(1700)
        QTimer.singleShot(3500,self.refresh)
    def wrap(self,widget):
        outer=QScrollArea();outer.setWidgetResizable(True);outer.setFrameShape(QFrame.NoFrame)
        outer.setWidget(widget);return outer
    def view(self):
        frame=QWidget();layout=QVBoxLayout(frame);layout.setSpacing(14)
        return frame,layout
    def build_dashboard(self):
        page,l=self.view();hero=card();h=QVBoxLayout(hero)
        title=QLabel('Your workstation, in control.');title.setObjectName('hero');h.addWidget(title)
        h.addWidget(QLabel('Choose a workload, inspect performance, or review Windows settings.'));l.addWidget(hero)
        grid=QGridLayout()
        for i,name in enumerate(['CPU','RAM','Disk','GPU']):
            c=card();v=QVBoxLayout(c);v.addWidget(QLabel(name.upper()))
            val=QLabel('—');val.setObjectName('metric');v.addWidget(val)
            self.metric[name]=val;grid.addWidget(c,0,i)
        l.addLayout(grid)
        main=QHBoxLayout();modes=card();ml=QVBoxLayout(modes)
        ml.addWidget(QLabel('QUICK MODES'))
        for name in ('Gaming','3D / Rendering','Roblox Studio / Dev','Work / Productivity','Quiet / Battery'):
            b=QPushButton(name+'     →');b.clicked.connect(lambda _,n=name:self.apply_preset(n));ml.addWidget(b)
        ml.addStretch();main.addWidget(modes)
        insight=card();il=QVBoxLayout(insight);il.addWidget(QLabel('WORKLOAD INSIGHTS'))
        self.insights=QLabel('Gathering readings...');self.insights.setWordWrap(True);il.addWidget(self.insights)
        il.addStretch();main.addWidget(insight);l.addLayout(main)
        c=card();cl=QVBoxLayout(c);cl.addWidget(QLabel('RESOURCE TRENDS   •   CPU / RAM / GPU'))
        self.chart=Trends();cl.addWidget(self.chart);l.addWidget(c)
        return self.wrap(page)
    def build_optimizations(self):
        page,l=self.view();self.search=QLineEdit();self.search.setPlaceholderText('Search settings...')
        l.addWidget(self.search)
        self.tweak_holder=QVBoxLayout();l.addLayout(self.tweak_holder)
        self.search.textChanged.connect(self.populate_tweaks);self.populate_tweaks()
        return self.wrap(page)
    def populate_tweaks(self):
        while self.tweak_holder.count():
            item=self.tweak_holder.takeAt(0)
            if item.widget():item.widget().deleteLater()
        query=self.search.text().lower()
        for key,t in TW.items():
            if query not in (t.name+' '+t.desc+' '+t.category).lower():continue
            c=card();row=QHBoxLayout(c);texts=QVBoxLayout()
            texts.addWidget(QLabel(t.name))
            desc=QLabel(t.desc);desc.setWordWrap(True);desc.setObjectName('muted');texts.addWidget(desc)
            row.addLayout(texts,1);button=QPushButton('Review')
            button.clicked.connect(lambda _,k=key:self.review_tweak(k));row.addWidget(button)
            self.tweak_holder.addWidget(c)
    def build_presets(self):
        page,l=self.view()
        for name in self.backend.data['profiles']:
            b=QPushButton('Apply preset: '+name);b.clicked.connect(lambda _,n=name:self.apply_preset(n));l.addWidget(b)
        l.addStretch();return self.wrap(page)
    def build_snapshots(self):
        page,l=self.view()
        for index,item in reversed(list(enumerate(self.backend.data['history']))):
            b=QPushButton('Restore: '+str(item.get('label','Snapshot')))
            b.clicked.connect(lambda _,i=index:self.rollback(i));l.addWidget(b)
        l.addStretch();return self.wrap(page)
    def build_hardware(self):
        page,l=self.view();self.hardware_text=QLabel('Detecting hardware...')
        self.hardware_text.setWordWrap(True);l.addWidget(self.hardware_text);l.addStretch()
        return self.wrap(page)
    def build_settings(self):
        page,l=self.view();l.addWidget(QLabel('Appearance'))
        picker=QComboBox();picker.addItems(STYLES);picker.setCurrentText(self.backend.data.get('theme','Amber Night'))
        picker.currentTextChanged.connect(self.set_theme);l.addWidget(picker)
        l.addWidget(QLabel('Updates are downloaded only after your approval.'))
        l.addStretch();return self.wrap(page)
    def apply_theme(self,name):
        bg,panel,raised,accent=STYLES.get(name,STYLES['Amber Night'])
        self.setStyleSheet(f"""
          QWidget {{background:{bg};color:#eef4ff;font: 11pt 'Segoe UI';}}
          QFrame#sidebar {{background:{panel};border-right:1px solid {raised};}}
          QFrame#card {{background:{panel};border-radius:17px;}}
          QLabel#heading {{font-size:25px;font-weight:700;}}
          QLabel#hero {{font-size:22px;font-weight:700;}}
          QLabel#metric {{font-size:26px;font-weight:700;}}
          QLabel#brand {{font-size:17px;font-weight:800;color:{accent};}}
          QLabel#muted {{color:#a5b4c8;font-size:10pt;}}
          QPushButton {{background:{raised};border:0;border-radius:11px;padding:12px 16px;text-align:left;}}
          QPushButton:hover {{background:{accent};color:{bg};}}
          QPushButton:pressed {{background:{accent};}}
          QLineEdit,QComboBox {{background:{raised};border:1px solid #526077;border-radius:9px;padding:12px;}}
          QScrollArea {{border:0;}} QScrollBar:vertical {{width:9px;background:{bg};}}
          QScrollBar::handle:vertical {{background:{raised};border-radius:4px;min-height:34px;}}
          QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
        """)
    def set_theme(self,name):
        self.theme=name;self.backend.data['theme']=name;self.backend.save();self.apply_theme(name)
    def show_page(self,name):
        self.heading.setText(name);self.pages.setCurrentIndex(self.page_names.index(name))
    def refresh(self):
        info=self.telemetry.latest()
        if not info:return
        cpu=info.get('cpu_percent');ram=info.get('ram_percent');disk=info.get('disk_percent')
        gpus=info.get('gpus') or []
        gpu=max((g.get('utilization') for g in gpus if g.get('utilization') is not None),default=None)
        for name,val in [('CPU',cpu),('RAM',ram),('Disk',disk),('GPU',gpu)]:
            self.metric[name].setText(f'{val:.0f}%' if val is not None else 'N/A')
        self.chart.add(info)
        self.insights.setText('\n\n'.join(f'{a}: {b}' for a,b in recommendations(info)) or
                              'No major resource pressure detected.')
        self.hardware_text.setText(f"Memory: {info.get('ram_total_gib') or '?'} GiB\n"
                                   f"Detected workloads: {', '.join(info.get('workloads') or []) or 'None'}")
    def apply_preset(self,name):
        cfg=self.backend.data['profiles'].get(name)
        if not cfg:return
        changes={key:True for key in cfg['tweaks'] if key in TW}
        text='\n'.join('• '+TW[k].name for k in changes)
        if QMessageBox.question(self,'Confirm preset',f'{name}\n\n{text}\n\nApply with rollback snapshot?')!=QMessageBox.Yes:return
        try:self.backend.apply(changes,power=POWER_SCHEMES.get(cfg.get('power')),label=name)
        except Exception as exc:QMessageBox.warning(self,'Apply failed',str(exc))
    def review_tweak(self,key):
        item=TW[key]
        if QMessageBox.question(self,'Review setting',f'{item.name}\n\n{item.desc}\n\nApply and save original value?')!=QMessageBox.Yes:return
        try:self.backend.apply({key:True},label=item.name)
        except Exception as exc:QMessageBox.warning(self,'Apply failed',str(exc))
    def rollback(self,index):
        if QMessageBox.question(self,'Restore snapshot','Restore saved system state?')!=QMessageBox.Yes:return
        try:self.backend.rollback(index);QMessageBox.information(self,'Restored','Snapshot restored.')
        except Exception as exc:QMessageBox.warning(self,'Restore failed',str(exc))
    def check_updates(self):
        QMessageBox.information(self,'Update check','The stable Tkinter build remains the supported updater until Qt parity and Windows QA are complete.')
    def closeEvent(self,event):
        self.telemetry.stop();super().closeEvent(event)

def main():
    app=QApplication(sys.argv);win=Window();win.show()
    return app.exec()

if __name__=='__main__':sys.exit(main())
