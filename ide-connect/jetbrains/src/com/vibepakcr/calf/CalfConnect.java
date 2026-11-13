package com.vibepakcr.calf;
import com.google.gson.*;
import com.intellij.ide.util.PropertiesComponent;
import com.intellij.openapi.actionSystem.*;
import com.intellij.openapi.application.ApplicationManager;
import com.intellij.openapi.project.Project;
import com.intellij.openapi.ui.Messages;
import java.awt.datatransfer.StringSelection;
import com.intellij.openapi.ide.CopyPasteManager;

public final class CalfConnect {
  private static final String KEY="calf.connect.connection";
  private static String ask(Project p,String text){return Messages.showInputDialog(p,text,"CALF connection",null);}
  private static JsonObject saved(Project p){String raw=PropertiesComponent.getInstance(p).getValue(KEY);if(raw==null)throw new IllegalStateException("Configure this workspace connection first.");return JsonParser.parseString(raw).getAsJsonObject();}
  private static void message(Project p,String text){ApplicationManager.getApplication().invokeLater(()->{if(!p.isDisposed())Messages.showInfoMessage(p,text,"Native CALF response");});}
  private static void error(Project p,Exception e){ApplicationManager.getApplication().invokeLater(()->{if(!p.isDisposed())Messages.showErrorDialog(p,String.valueOf(e.getMessage()),"CALF connection");});}
  private static void work(Project p,Job job){ApplicationManager.getApplication().executeOnPooledThread(()->{try{job.run();}catch(Exception e){error(p,e);}});}
  private interface Job {void run()throws Exception;}
  public static class Configure extends AnAction {
    @Override public void actionPerformed(AnActionEvent e){Project p=e.getProject();if(p==null)return;
      String core=ask(p,"Existing CALF native core: absolute executable path");if(core==null)return;
      String home=ask(p,"Existing records folder: use the same folder as Workbench");if(home==null)return;
      String wb=ask(p,"Workbench native executable path (macOS: inside Contents/MacOS)");if(wb==null)return;
      work(p,()->{JsonObject c=Transport.configure(core,home,wb);ApplicationManager.getApplication().invokeLater(()->{if(!p.isDisposed()){PropertiesComponent.getInstance(p).setValue(KEY,c.toString());Messages.showInfoMessage(p,"Connection saved for this project. No task, model or tool was started.","CALF connection");}});});
    }
  }
  public static class Open extends AnAction {
    @Override public void actionPerformed(AnActionEvent e){Project p=e.getProject();if(p!=null)work(p,()->{Transport.open(saved(p));message(p,"Workbench launch requested with this records folder.");});}
  }
  public static class Attention extends AnAction {
    @Override public void actionPerformed(AnActionEvent e){Project p=e.getProject();if(p!=null)work(p,()->{String raw=new GsonBuilder().setPrettyPrinting().create().toJson(Transport.call(saved(p),"attention"));String limit=raw.length()>24000?raw.substring(0,24000)+"\n[Display shortened. Open Workbench for the full list.]":raw;message(p,"Native response; this connection does not decide completion or grant authority.\n\n"+limit);});}
  }
  public static class Mcp extends AnAction {
    @Override public void actionPerformed(AnActionEvent e){Project p=e.getProject();if(p!=null)work(p,()->{String raw=Transport.mcp(saved(p)).toString();ApplicationManager.getApplication().invokeLater(()->{if(!p.isDisposed()){CopyPasteManager.getInstance().setContents(new StringSelection(raw));Messages.showInfoMessage(p,"Copied a read-only stdio server entry. No client setting was changed.","CALF connection");}});});}
  }
}
