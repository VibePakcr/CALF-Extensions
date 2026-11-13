package com.vibepakcr.calf;
import com.google.gson.*;
import java.nio.file.*;
public final class TransportProbe {
 public static void main(String[] args)throws Exception {
  Path home=Path.of(args[1]);Files.createDirectory(home);JsonObject c=Transport.configure(args[0],home.toString(),args[0]);
  JsonObject value=Transport.call(c,"attention").getAsJsonObject();
  if(!value.get("readOnly").getAsBoolean()||value.get("completionEvaluated").getAsBoolean()||value.getAsJsonObject("coverage").get("wholeProject").getAsBoolean())throw new AssertionError("Native observation boundary");
  JsonArray mcp=Transport.mcp(c).getAsJsonArray("args");if(mcp.size()!=2||!mcp.get(0).getAsString().equals("work-mcp"))throw new AssertionError("MCP control flag");
  JsonObject literal=new JsonObject();literal.addProperty("home","/literal/한글 ' $(text)");JsonObject request=Transport.request("attention",literal);if(!request.getAsJsonObject("input").get("home").equals(literal.get("home")))throw new AssertionError("Literal transport");
  boolean denied=false;try{Transport.request("run",c);}catch(java.io.IOException e){denied=true;}if(!denied)throw new AssertionError("Unknown action");
  try(var paths=Files.list(home)){if(paths.count()!=0)throw new AssertionError("Unexpected record mutation");}
  System.out.println("{\"status\":\"PASS\",\"checks\":5,\"modelCalls\":0,\"nativeReadOnly\":true,\"controlEnabled\":false}");
 }
}
