def test_openapi_is_accessible(client):
    r = client.get("/openapi.json")
    r.raise_for_status()
    data = r.json()

    assert "openapi" in data
    assert "paths" in data


def test_openapi_operation_ids(client):
    data = client.get("/openapi.json").json()

    def op_id(path: str, method: str = "get") -> str:
        return data["paths"][path][method]["operationId"]

    assert op_id("/search") == "searchComplaints"
    assert op_id("/trends") == "listTrends"
    assert op_id("/geo/states") == "getGeoStates"
    assert op_id("/suggest/{field}") == "suggestFilterValues"
    assert op_id("/complaint/{complaint_id}") == "getComplaintDocument"

    assert op_id("/signals/overall") == "getOverallSignals"
    assert op_id("/signals/group") == "rankGroupSignals"
    assert op_id("/signals/company") == "rankCompanySignals"

    assert op_id("/cfpb-ui/url") == "generateCFPBDashboardUrl"
    assert op_id("/cfpb-ui/screenshot") == "screenshotCFPBDashboard"
