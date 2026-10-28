"""ModeShift Qt frontend preview. Does not alter the existing Tkinter entrypoint."""
from __future__ import annotations
import sys, os, threading, time, csv
from pathlib import Path
from collections import deque
from PySide6.QtCore import Qt, QTimer, QPointF, Signal, QObject
from PySide6.QtGui import QPainter, QPen, QColor
from PySide6.QtWidgets import (
    QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,QGridLayout,
    QLabel,QPushButton,QFrame,QScrollArea,QStackedWidget,QMessageBox,
    QComboBox,QLineEdit,QCheckBox,QSizePolicy,QGraphicsDropShadowEffect,QFileDialog
)
from modeshift import Backend,TelemetrySampler,TW,POWER_SCHEMES, recommendations, recommend_profile, assess_unattended, GUARD_DEFAULTS, ROOT, persist, AUTOMATION_DEFAULTS, GUARD_FILE, write_guard_event
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

class UpdateSignals(QObject):
    ready=Signal(object)
    error=Signal(str)
    staged=Signal(object,object,object,object)

class Window(QMainWindow):
    def __init__(self):
        super().__init__()
        self.backend=Backend();self.telemetry=TelemetrySampler()
        self.setWindowTitle('ModeShift — Qt Preview')
        self.resize(1330,850)
        self.root=QWidget();self.setCentralWidget(self.root)
        self.layout=QHBoxLayout(self.root);self.layout.setContentsMargins(0,0,0,0);self.layout.setSpacing(0)
        self.nav=QFrame();self.nav.setObjectName('sidebar');self.nav.setFixedWidth(236)
        nv=QVBoxLayout(self.nav);nv.setContentsMargins(15,28,15,20);nv.setSpacing(3)
        logo=QLabel('◈  MODESHIFT');logo.setObjectName('brand');nv.addWidget(logo)
        sub=QLabel('WORKSTATION CONTROL');sub.setObjectName('eyebrow');nv.addWidget(sub)
        nv.addSpacing(29)
        self.pages=QStackedWidget()
        self.nav_buttons={}
        groups=[
            ('OVERVIEW',['Dashboard','Hardware']),
            ('WORKFLOWS',['Optimizations','Presets','Automation','Unattended']),
            ('YOUR SYSTEM',['Measurements','Snapshots','Settings']),
        ]
        symbols={'Dashboard':'⌂','Hardware':'▦','Optimizations':'☷',
                 'Presets':'◈','Automation':'⟳','Unattended':'☾','Measurements':'▤','Snapshots':'↶','Settings':'⚙'}
        for group,names in groups:
            section=QLabel(group);section.setObjectName('section')
            nv.addWidget(section)
            for name in names:
                button=QPushButton(f"{symbols[name]}    {name}")
                button.setObjectName('navButton');button.setCursor(Qt.PointingHandCursor)
                button.clicked.connect(lambda _,n=name:self.show_page(n))
                nv.addWidget(button);self.nav_buttons[name]=button
            nv.addSpacing(15)
        nv.addStretch()
        status=QLabel('●  LOCAL · PRIVATE · FREE');status.setObjectName('footnote')
        nv.addWidget(status)
        self.layout.addWidget(self.nav)
        body=QFrame();bl=QVBoxLayout(body);bl.setContentsMargins(30,26,30,24);bl.setSpacing(18)
        top=QHBoxLayout();self.heading=QLabel('Dashboard');self.heading.setObjectName('heading');top.addWidget(self.heading)
        top.addStretch()
        self.update_btn=QPushButton('↻  Check updates');self.update_btn.setObjectName('secondaryButton');self.update_btn.clicked.connect(self.check_updates);top.addWidget(self.update_btn)
        bl.addLayout(top);bl.addWidget(self.pages,1);self.layout.addWidget(body,1)
        self.page_names=['Dashboard','Optimizations','Presets','Automation','Unattended','Measurements','Snapshots','Hardware','Settings']
        self.metric={}
        self.recording=False
        self.recorded=[]
        self.last_guard_log=0.0
        self.update_signals=UpdateSignals()
        self.update_signals.ready.connect(self.update_available)
        self.update_signals.error.connect(self.update_error)
        self.update_signals.staged.connect(self.launch_staged_update)
        self.available_release=None
        for name in self.page_names:
            builder=getattr(self,'build_'+name.lower())
            self.pages.addWidget(builder())
        self.theme=self.backend.data.get('theme','Amber Night')
        self.apply_theme(self.theme);self.show_page('Dashboard')
        self.timer=QTimer(self);self.timer.timeout.connect(self.refresh);self.timer.start(1700)
        self.update_timer=QTimer(self);self.update_timer.timeout.connect(self.check_updates);self.update_timer.start(60*60*1000)
        QTimer.singleShot(3500,self.refresh)
    def wrap(self,widget):
        outer=QScrollArea();outer.setWidgetResizable(True);outer.setFrameShape(QFrame.NoFrame)
        outer.setWidget(widget);outer.verticalScrollBar().setSingleStep(25);return outer
    def view(self):
        frame=QWidget();layout=QVBoxLayout(frame);layout.setContentsMargins(1,1,12,12);layout.setSpacing(17)
        return frame,layout
    def build_dashboard(self):
        page,l=self.view();hero=card();hero.setObjectName('heroCard');h=QVBoxLayout(hero);h.setContentsMargins(25,25,25,25)
        tag=QLabel('SYSTEM OVERVIEW');tag.setObjectName('eyebrow');h.addWidget(tag)
        title=QLabel('Your workstation, in control.');title.setObjectName('hero');h.addWidget(title)
        h.addWidget(QLabel('Choose a workload, inspect performance, or review Windows settings.'));l.addWidget(hero)
        grid=QGridLayout()
        for i,name in enumerate(['CPU','RAM','Disk','GPU']):
            c=card();v=QVBoxLayout(c);v.setContentsMargins(20,16,20,18)
            label=QLabel(name.upper());label.setObjectName('eyebrow');v.addWidget(label)
            val=QLabel('—');val.setObjectName('metric');v.addWidget(val)
            self.metric[name]=val;grid.addWidget(c,0,i)
        l.addLayout(grid)
        main=QHBoxLayout();main.setSpacing(17);modes=card();ml=QVBoxLayout(modes);ml.setContentsMargins(20,20,20,20);ml.setSpacing(9)
        heading=QLabel('QUICK WORKLOADS');heading.setObjectName('eyebrow');ml.addWidget(heading)
        for name in ('Gaming','3D / Rendering','Roblox Studio / Dev','Work / Productivity','Quiet / Battery'):
            b=QPushButton(name+'     →');b.setObjectName('modeButton');b.setCursor(Qt.PointingHandCursor);b.clicked.connect(lambda _,n=name:self.apply_preset(n));ml.addWidget(b)
        ml.addStretch();main.addWidget(modes,1)
        insight=card();il=QVBoxLayout(insight);il.setContentsMargins(22,21,22,21)
        label=QLabel('WORKLOAD INSIGHTS');label.setObjectName('eyebrow');il.addWidget(label)
        self.insights=QLabel('Gathering readings...');self.insights.setWordWrap(True);il.addWidget(self.insights)
        il.addStretch();main.addWidget(insight,1);l.addLayout(main)
        c=card();cl=QVBoxLayout(c);cl.setContentsMargins(22,20,22,18)
        ct=QLabel('LIVE RESOURCE TRENDS    ·    CPU / RAM / GPU');ct.setObjectName('eyebrow');cl.addWidget(ct)
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
    def build_automation(self):
        page,l=self.view()
        block=card();v=QVBoxLayout(block)
        v.addWidget(QLabel('AUTOMATIC WORKLOAD RECOGNITION'))
        v.addWidget(QLabel('Qt preview: detect workloads and recommend a matching profile; no automatic system changes.'))
        self.auto_switch=QCheckBox('Enable workload detection (recommendations only in Qt preview)')
        self.auto_switch.setChecked(bool(self.backend.data['automation']['enabled']))
        self.auto_switch.toggled.connect(self.save_automation)
        v.addWidget(self.auto_switch)
        self.auto_status=QLabel('Waiting for a workload sample...')
        v.addWidget(self.auto_status)
        l.addWidget(block)
        self.auto_mapping={}
        for workload,profile in self.backend.data['automation']['mapping'].items():
            row=card();h=QHBoxLayout(row);h.addWidget(QLabel(workload),1)
            picker=QComboBox();picker.addItems(['None']+list(self.backend.data['profiles']))
            picker.setCurrentText(profile if profile in self.backend.data['profiles'] else 'None')
            picker.currentTextChanged.connect(lambda value,k=workload:self.set_auto_mapping(k,value))
            h.addWidget(picker);self.auto_mapping[workload]=picker;l.addWidget(row)
        l.addStretch();return self.wrap(page)
    def save_automation(self,enabled):
        self.backend.data['automation']['enabled']=bool(enabled);self.backend.save()
    def set_auto_mapping(self,workload,value):
        self.backend.data['automation']['mapping'][workload]=value
        self.backend.save()
    def build_unattended(self):
        page,l=self.view();c=card();v=QVBoxLayout(c)
        v.addWidget(QLabel('UNATTENDED DEVELOPMENT + RENDERING'))
        info=QLabel('Advisory monitoring only. Never automatically kills Blender, Roblox Studio or Claude jobs.')
        info.setWordWrap(True);v.addWidget(info)
        self.guard_switch=QCheckBox('Enable resource pressure logging')
        self.guard_switch.setChecked(bool(self.backend.data['unattended_guard']['enabled']))
        self.guard_switch.toggled.connect(self.save_guard)
        v.addWidget(self.guard_switch)
        self.guard_status=QLabel('Waiting for a sample...')
        self.guard_status.setWordWrap(True);v.addWidget(self.guard_status)
        l.addWidget(c);l.addStretch();return self.wrap(page)
    def save_guard(self,enabled):
        self.backend.data['unattended_guard']['enabled']=bool(enabled);self.backend.save()
    def build_measurements(self):
        page,l=self.view();c=card();v=QVBoxLayout(c)
        v.addWidget(QLabel('RESOURCE SESSION RECORDER'))
        self.measure_status=QLabel('Not recording');v.addWidget(self.measure_status)
        self.record_button=QPushButton('Start recording')
        self.record_button.clicked.connect(self.toggle_recording);v.addWidget(self.record_button)
        export=QPushButton('Export session as CSV');export.clicked.connect(self.export_recording)
        v.addWidget(export);l.addWidget(c);l.addStretch();return self.wrap(page)
    def toggle_recording(self):
        self.recording=not self.recording
        if self.recording:self.recorded=[]
        self.record_button.setText('Stop recording' if self.recording else 'Start recording')
        self.measure_status.setText('Recording...' if self.recording else f'Session captured: {len(self.recorded)} samples')
    def export_recording(self):
        if not self.recorded:
            QMessageBox.information(self,'No samples','Start a recording before exporting.');return
        filename,_=QFileDialog.getSaveFileName(self,'Export samples','modeshift-session.csv','CSV files (*.csv)')
        if filename:
            with open(filename,'w',newline='',encoding='utf-8') as out:
                writer=csv.DictWriter(out,fieldnames=['time','cpu','ram','disk','gpu'])
                writer.writeheader();writer.writerows(self.recorded)
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
          QWidget {{background:{bg};color:#eef4ff;font: 10pt 'Segoe UI';}}
          QFrame#sidebar {{background:{panel};border-right:1px solid {raised};}}
          QFrame#card {{background:{panel};border:1px solid {raised};border-radius:18px;}}
          QFrame#heroCard {{background:{panel};border:1px solid {raised};border-radius:21px;}}
          QLabel {{background:transparent;}}
          QLabel#heading {{font-size:24px;font-weight:700;}}
          QLabel#hero {{font-size:23px;font-weight:700;}}
          QLabel#metric {{font-size:25px;font-weight:700;}}
          QLabel#brand {{font-size:17px;font-weight:800;color:{accent};}}
          QLabel#eyebrow {{font-size:9px;letter-spacing:1px;font-weight:700;color:{accent};}}
          QLabel#section {{font-size:9px;font-weight:700;color:#8291a8;margin-top:5px;margin-bottom:4px;}}
          QLabel#footnote {{font-size:9px;color:#8291a8;}}
          QLabel#muted {{color:#a5b4c8;font-size:10pt;}}
          QPushButton {{background:{raised};border:1px solid transparent;border-radius:12px;
                        padding:12px 16px;text-align:left;font-weight:600;}}
          QPushButton:hover {{background:{accent};color:{bg};}}
          QPushButton:pressed {{background:{accent};}}
          QPushButton#navButton {{background:transparent;color:#a5b4c8;padding:12px 14px;}}
          QPushButton#navButton:hover {{background:{raised};color:#ffffff;}}
          QPushButton#navButton[active="true"] {{background:{raised};color:{accent};border-left:3px solid {accent};}}
          QPushButton#modeButton {{padding:14px;background:{raised};}}
          QPushButton#modeButton:hover {{background:{accent};color:{bg};}}
          QPushButton#secondaryButton {{padding:10px 18px;}}
          QLineEdit,QComboBox {{background:{raised};border:1px solid #526077;border-radius:10px;padding:12px;}}
          QScrollArea {{border:0;}} QScrollBar:vertical {{width:10px;background:{bg};}}
          QScrollBar::handle:vertical {{background:{raised};border-radius:5px;min-height:36px;}}
          QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical {{height:0;}}
        """)
    def set_theme(self,name):
        self.theme=name;self.backend.data['theme']=name;self.backend.save();self.apply_theme(name)
    def active_name(self):
        return self.page_names[self.pages.currentIndex()]
    def show_page(self,name):
        self.heading.setText(name)
        self.pages.setCurrentIndex(self.page_names.index(name))
        for label,button in self.nav_buttons.items():
            button.setProperty('active',label==name)
            button.style().unpolish(button)
            button.style().polish(button)
    def refresh(self):
        info=self.telemetry.latest()
        if not info:return
        cpu=info.get('cpu_percent');ram=info.get('ram_percent');disk=info.get('disk_percent')
        gpus=info.get('gpus') or []
        gpu=max((g.get('utilization') for g in gpus if g.get('utilization') is not None),default=None)
        for name,val in [('CPU',cpu),('RAM',ram),('Disk',disk),('GPU',gpu)]:
            self.metric[name].setText(f'{val:.0f}%' if val is not None else 'N/A')
        self.chart.add(info)
        if self.recording:
            gpus=info.get('gpus') or []
            gpu=max((g.get('utilization') for g in gpus if g.get('utilization') is not None),default=None)
            self.recorded.append({'time':time.time(),'cpu':cpu,'ram':ram,'disk':disk,'gpu':gpu})
            if self.active_name()=='Measurements':
                self.measure_status.setText(f'Recording: {len(self.recorded)} samples')
        if self.backend.data['unattended_guard']['enabled']:
            findings=assess_unattended(info,self.backend.data['unattended_guard'])
            self.guard_status.setText('\n'.join(f'{level}: {message}' for level,message in findings) or 'No resource threshold exceeded.')
            now=time.monotonic()
            if now-self.last_guard_log>=max(20,self.backend.data['unattended_guard']['log_interval_s']):
                try:write_guard_event(GUARD_FILE,info,findings)
                except OSError as exc:self.statusBar().showMessage('Guard log unavailable: '+str(exc),8000)
                self.last_guard_log=now
        if self.backend.data['automation']['enabled']:
            choice=recommend_profile(info.get('workloads') or [],self.backend.data['automation']['mapping'],self.backend.data['profiles'])
            self.auto_status.setText('Detected: '+(', '.join(info.get('workloads') or []) or 'Idle')+' · Suggested: '+str(choice or 'Balanced'))
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
        if getattr(self,'update_check_busy',False):return
        self.update_check_busy=True
        self.update_btn.setText('Checking…')
        url=self.backend.data.get('update_manifest') or 'https://github.com/lolipopkins/ModeShift/releases/latest/download/latest.json'
        def work():
            try:self.update_signals.ready.emit(updater.check(url))
            except Exception as exc:self.update_signals.error.emit(str(exc))
        threading.Thread(target=work,daemon=True).start()
    def update_error(self,error):
        self.update_check_busy=False;self.install_busy=False;self.update_btn.setText('↻  Check updates')
        self.statusBar().showMessage('Update check unavailable: '+error[:130],10000)
    def update_available(self,release):
        self.update_check_busy=False;self.update_btn.setText('↻  Check updates')
        if not release.get('available'):
            self.statusBar().showMessage('ModeShift is up to date',7000);return
        self.available_release=release
        answer=QMessageBox.question(self,'Update available',
            f"ModeShift {release['version']} is available.\n\nInstall and restart?\nSave any active work before updating.",
            QMessageBox.Yes|QMessageBox.No,QMessageBox.No)
        if answer==QMessageBox.Yes:self.install_update(release)
    def install_update(self,release):
        if not getattr(sys,'frozen',False) or os.name!='nt':
            QMessageBox.information(self,'Preview mode','The Qt source preview cannot self-update.');return
        if getattr(self,'install_busy',False):return
        self.install_busy=True
        self.update_btn.setText('Downloading update…')
        installed=(Path(sys.executable).parent/'unins000.exe').is_file()
        url=release.get('installer_url') if installed else release['url']
        digest=release.get('installer_sha256') if installed else release['sha256']
        if not url or not digest:
            self.install_busy=False;self.update_error('No verified installer in release');return
        folder=ROOT/'updates';folder.mkdir(parents=True,exist_ok=True)
        def work():
            try:
                staged=updater.download_verified({'url':url,'sha256':digest},
                    folder/('ModeShiftSetup-update.exe' if installed else 'ModeShift-update.exe'))
                self.update_signals.staged.emit(installed,staged,digest,folder)
            except Exception as exc:
                self.update_signals.error.emit(str(exc))
        threading.Thread(target=work,daemon=True).start()
    def launch_staged_update(self,installed,staged,digest,folder):
        try:
            if installed:updater.start_installer_upgrade(sys.executable,staged,digest,folder)
            else:updater.start_replacement(sys.executable,staged,digest,folder)
            self.close()
        except Exception as exc:
            self.install_busy=False
            self.update_error(str(exc))
    def closeEvent(self,event):
        self.telemetry.stop();super().closeEvent(event)

def main():
    app=QApplication(sys.argv);win=Window();win.show()
    return app.exec()

if __name__=='__main__':sys.exit(main())
