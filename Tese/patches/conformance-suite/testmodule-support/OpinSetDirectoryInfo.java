package net.openid.conformance.opin.testmodule.support;

import com.google.gson.JsonObject;
import net.openid.conformance.condition.AbstractCondition;
import net.openid.conformance.testmodule.Environment;

public class OpinSetDirectoryInfo extends AbstractCondition {

    private final String BRAZIL_DIRECTORY_DISCOVERY_URL = "https://auth.sandbox.directory.opinbrasil.com.br/.well-known/openid-configuration";
	private final String BRAZIL_DIRECTORY_API_BASE = "https://matls-api.sandbox.directory.opinbrasil.com.br/";

	private final String BRAZIL_DIRECTORY_KEYSTORE_URL = "https://keystore.sandbox.directory.opinbrasil.com.br/";

	@Override
	public Environment evaluate(Environment env) {

		var config = env.getObject("config");
		String discoveryUrl = env.getString("config", "directory.discoveryUrl");
		String apiBase = env.getString("config", "directory.apibase");
		String keystore = env.getString("config", "directory.keystore");
		JsonObject directoryObj = new JsonObject();
		directoryObj.addProperty("discoveryUrl", discoveryUrl != null ? discoveryUrl : BRAZIL_DIRECTORY_DISCOVERY_URL);
		directoryObj.addProperty("client_id", env.getString("config", "directory.client_id"));
		directoryObj.addProperty("apibase", apiBase != null ? apiBase : BRAZIL_DIRECTORY_API_BASE);
		directoryObj.addProperty("keystore", keystore != null ? keystore : BRAZIL_DIRECTORY_KEYSTORE_URL);
		config.add("directory", directoryObj);

		//log("Env:\n" + env.toString());

		return env;
	}
}
