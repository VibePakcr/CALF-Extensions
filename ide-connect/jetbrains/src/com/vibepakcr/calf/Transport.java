package com.vibepakcr.calf;
import com.google.gson.*;
import java.nio.file.*;
import java.io.*;
import java.security.MessageDigest;
import java.util.*;
import java.util.concurrent.*;

public final class Transport {
  private static final Gson JSON=new Gson();
  private static JsonObject contract() throws IOException {
    try(InputStream input=Transport.class.getResourceAsStream("/calf-connect-contract.json")){
      if(input==null)throw new IOException("Missing bundled transport descriptor.");
      return JsonParser.parseString(new String(input.readAllBytes(),java.nio.charset.StandardCharsets.UTF_8)).getAsJsonObject();
    }
  }
  private static String physical(String path,boolean directory)throws IOException {
    Path p=Path.of(path);if(!p.isAbsolute())throw new IOException("Use an absolute existing path.");
    p=p.toRealPath();if(directory&&!Files.isDirectory(p))throw new IOException("Choose an existing records folder.");return p.toString();
  }
  private static String hash(String path)throws Exception {
    Path p=Path.of(path);if(!Files.isRegularFile(p)||Files.size(p)>128L*1024*1024)throw new IOException("Choose an existing native executable (at most 128 MiB).");
    MessageDigest digest=MessageDigest.getInstance("SHA-256");try(InputStream in=Files.newInputStream(p)){byte[] block=new byte[65536];for(int n;(n=in.read(block))!=-1;)digest.update(block,0,n);}
    return HexFormat.of().formatHex(digest.digest());
  }
  public static JsonObject configure(String core,String home,String workbench)throws Exception{
    JsonObject c=new JsonObject();c.addProperty("schema",1);c.addProperty("core",physical(core,false));c.addProperty("home",physical(home,true));c.addProperty("workbench",physical(workbench,false));c.addProperty("coreSha256",hash(c.get("core").getAsString()));c.addProperty("workbenchSha256",hash(c.get("workbench").getAsString()));return c;
  }
  public static void check(JsonObject c)throws Exception {
    if(c.get("schema").getAsInt()!=1||!physical(c.get("home").getAsString(),true).equals(c.get("home").getAsString())||!hash(c.get("core").getAsString()).equals(c.get("coreSha256").getAsString())||!hash(c.get("workbench").getAsString()).equals(c.get("workbenchSha256").getAsString()))throw new IOException("Connection identity changed. Configure it again; no substitution was made.");
  }
  private static JsonElement expand(JsonElement v,JsonObject c){
    if(v.isJsonObject()){JsonObject out=new JsonObject();v.getAsJsonObject().entrySet().forEach(e->out.add(e.getKey(),expand(e.getValue(),c)));return out;}
    if(v.isJsonArray()){JsonArray out=new JsonArray();v.getAsJsonArray().forEach(e->out.add(expand(e,c)));return out;}
    if(v.isJsonPrimitive()&&v.getAsJsonPrimitive().isString()&&v.getAsString().startsWith("$"))return Objects.requireNonNull(c.get(v.getAsString().substring(1)),"Missing connection value.").deepCopy();
    return v.deepCopy();
  }
  public static JsonObject request(String action,JsonObject c)throws IOException{
    JsonObject definition=contract().getAsJsonObject("actions").getAsJsonObject(action);if(definition==null)throw new IOException("Unsupported connection action.");
    JsonObject result=new JsonObject();result.add("args",expand(definition.get("arguments"),c));result.add("input",expand(definition.get("input"),c));return result;
  }
  public static JsonObject mcp(JsonObject c)throws Exception{
    check(c);JsonObject value=new JsonObject();value.add("command",c.get("core"));value.add("args",expand(contract().getAsJsonObject("mcp").get("arguments"),c));return value;
  }
  public static JsonElement call(JsonObject c,String action)throws Exception {
    check(c);JsonObject request=request(action,c);List<String> args=new ArrayList<>();args.add(c.get("core").getAsString());request.getAsJsonArray("args").forEach(v->args.add(v.getAsString()));
    ProcessBuilder builder=new ProcessBuilder(args).redirectErrorStream(true);builder.environment().put("CALF_WORK_HOME",c.get("home").getAsString());Process process=builder.start();ExecutorService reader=Executors.newSingleThreadExecutor();
    try{
      Future<byte[]> output=reader.submit(()->process.getInputStream().readNBytes(1024*1024+1));
      try(OutputStream in=process.getOutputStream()){in.write(JSON.toJson(request.get("input")).getBytes(java.nio.charset.StandardCharsets.UTF_8));}
      if(!process.waitFor(30,TimeUnit.SECONDS)){process.destroyForcibly();throw new IOException("No confirmed CALF response. Inspect existing records; no retry was attempted.");}
      byte[] raw=output.get(2,TimeUnit.SECONDS);if(process.exitValue()!=0||raw.length>1024*1024)throw new IOException("CALF did not return a bounded response. No retry was attempted.");
      check(c);JsonElement result=JsonParser.parseString(new String(raw,java.nio.charset.StandardCharsets.UTF_8));if(result.isJsonObject()&&result.getAsJsonObject().has("error"))throw new IOException("CALF returned an error: "+result.getAsJsonObject().get("error"));return result;
    }finally{process.getInputStream().close();if(process.isAlive())process.destroyForcibly();reader.shutdownNow();}
  }
  public static void open(JsonObject c)throws Exception {
    check(c);ProcessBuilder builder=new ProcessBuilder(c.get("workbench").getAsString()).redirectOutput(ProcessBuilder.Redirect.DISCARD).redirectError(ProcessBuilder.Redirect.DISCARD);
    builder.environment().put("CALF_WORK_HOME",c.get("home").getAsString());builder.start();
  }
}
