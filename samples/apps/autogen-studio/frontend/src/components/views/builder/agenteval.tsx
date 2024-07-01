import {
  ArrowDownTrayIcon,
  ArrowUpTrayIcon,
  DocumentDuplicateIcon,
  InformationCircleIcon,
  PlusIcon,
  TrashIcon,
  UserGroupIcon,
  UsersIcon,
} from "@heroicons/react/24/outline";
import { Dropdown, MenuProps, Modal, message } from "antd";
import * as React from "react";
import { IAgentEvalCriteria as IAgentEvalCriteria, IModelConfig, IStatus } from "../../types";
import { appContext } from "../../../hooks/provider";
import {
  fetchJSON,
  getServerUrl,
  sampleWorkflowConfig,
  sanitizeConfig,
  timeAgo,
  truncateText,
} from "../../utils";
import { BounceLoader, Card, CardHoverBar, LoadingOverlay } from "../../atoms";
import { CriteriaViewer } from "./utils/agentevalconfig";
  
const AgentEvalView = ({}: any) => {
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<IStatus | null>({
    status: true,
    message: "All good",
  });
  const { user } = React.useContext(appContext);
  const serverUrl = getServerUrl();
  const listCriteriaUrl = `${serverUrl}/agenteval/criteria`;
  const createCriteriaUrl = `${serverUrl}/agenteval/criteria/{criteria_id}`;
  const generateCriteriaUrl = `${serverUrl}/agenteval/criteria/generate`;

  const [criteria_list, setCriteria] = React.useState<IAgentEvalCriteria[] | null>([]);
  const [selectedCriteria, setSelectedCriteria] =
    React.useState<IAgentEvalCriteria | null>(null);

  const defaultConfig = sampleWorkflowConfig();
  // const [newCriteria, setNewCriteria] = React.useState<IAgentEvalCriteria | null>(
  //   defaultConfig
  // );

  const [showCriteriaModal, setShowCriteriaModal] = React.useState(false);
  const [showNewWorkflowModal, setShowNewWorkflowModal] = React.useState(false);

  const fetchCriteria = () => {
    setError(null);
    setLoading(true);
    // const fetch;
    const payLoad = {
      method: "GET",
      headers: {
        "Content-Type": "application/json",
      },
    };

    const onSuccess = (data: any) => {
      if (data) {
        console.log(data)
        setCriteria(data);
      } else {
        message.error(data.message);
      }
      setLoading(false);
    };
    const onError = (err: any) => {
      setError(err);
      message.error(err.message);
      setLoading(false);
    };
    fetchJSON(listCriteriaUrl, payLoad, onSuccess, onError);
  };

  const deleteCriteria = (criteria: IAgentEvalCriteria) => {
    setError(null);
    setLoading(true);
    // const fetch;
    const deleteWorkflowsUrl = `${serverUrl}/agenteval/criteria/delete/${criteria.id}`;
    const payLoad = {
      method: "DELETE",
      headers: {
        "Content-Type": "application/json",
      },
    };

    const onSuccess = (data: any) => {
      if (data && data.status) {
        message.success(data.message);
        fetchCriteria();
      } else {
        message.error(data.message);
      }
      setLoading(false);
    };
    const onError = (err: any) => {
      setError(err);
      message.error(err.message);
      setLoading(false);
    };
    fetchJSON(deleteWorkflowsUrl, payLoad, onSuccess, onError);
  };

  React.useEffect(() => {
    console.log("user: " + user)
    if (user) {
      console.log("fetching messages", message);
      fetchCriteria();
      console.log("done fetching", message);
    }
  }, []);

  React.useEffect(() => {
    if (selectedCriteria) {
      setShowCriteriaModal(true);
    }
  }, [selectedCriteria]);

  const criteriaRows = (criteria_list || []).map(
    (criteria: IAgentEvalCriteria, i: number) => {
      const cardItems = [
        {
          title: "Download",
          icon: ArrowDownTrayIcon,
          onClick: (e: any) => {
            e.stopPropagation();
            // download workflow as workflow.name.json
            const element = document.createElement("a");
            const criteria_json = criteria.criteria;
            const file = new Blob([criteria_json], {
              type: "application/json",
            });
            element.href = URL.createObjectURL(file);
            element.download = `criteria.json`;
            document.body.appendChild(element); // Required for this to work in FireFox
            element.click();
          },
          hoverText: "Download",
        },
        {
          title: "Delete",
          icon: TrashIcon,
          onClick: (e: any) => {
            e.stopPropagation();
            deleteCriteria(criteria);
          },
          hoverText: "Delete",
        },
      ];
      return (
        <li
          key={"workflowrow" + i}
          className="block   h-full"
          style={{ width: "200px" }}
        >
          <Card
            className="  block p-2 cursor-pointer"
            onClick={() => {
              setSelectedCriteria(criteria);
            }}
          >
            <div
              style={{ minHeight: "65px" }}
              className="break-words  my-2"
              aria-hidden="true"
            >
              {" "}
              {truncateText(criteria.task_name, 70)}
            </div>
            {<CardHoverBar items={cardItems} />}
          </Card>
        </li>
      );
    }
  );

  const CriteriaModal = ({
    criteria,
    setCriteria,
    showModal,
    setShowModal,
    handler,
  }: {
    criteria: IAgentEvalCriteria | null;
    setCriteria?: (criteria: IAgentEvalCriteria | null) => void;
    showModal: boolean;
    setShowModal: (show: boolean) => void;
    handler?: (workflow: IAgentEvalCriteria) => void;
  }) => {
    const [localCriteria, setLocalCriteria] = React.useState<IAgentEvalCriteria | null>(criteria);

    const closeModal = () => {
      setShowModal(false);
      if (handler) {
        handler(localCriteria as IAgentEvalCriteria);
      }
    };

    
    const [models, setModels] = React.useState<IModelConfig[]>([]);
    const { user } = React.useContext(appContext);

    React.useEffect(() => {
      const fetchModels = async () => {
        const serverUrl = getServerUrl();
        const listModelsUrl = `${serverUrl}/models?user_id=${user?.email}`;
        const payLoad = {
          method: "GET",
          headers: {
            "Content-Type": "application/json",
          },
        };

        const onSuccess = (data: any) => {
          if (data && data.status) {
            setModels(data.data);
          } else {
            message.error(data.message);
          }
          setLoading(false);
        };
        const onError = (err: any) => {
          setError(err);
          message.error(err.message);
          setLoading(false);
        };

        fetchJSON(listModelsUrl, payLoad, onSuccess, onError);
      };
  
      fetchModels();
    }, []);

    return (
      <Modal
        title={
          <>
            Criteria Details{" "}
            <span className="text-accent font-normal">
              {localCriteria?.task_name}
            </span>{" "}
          </>
        }
        width={800}
        open={showModal}
        onOk={() => {
          closeModal();
        }}
        onCancel={() => {
          closeModal();
        }}
        footer={[]}
      >
        <>
          {localCriteria && (
            <CriteriaViewer
              criteria={localCriteria}
              setCriteria={setLocalCriteria}
              models={models}
              close={closeModal}
            />
          )}
        </>
      </Modal>
    );
  };

  const showCriteria = (config: IAgentEvalCriteria) => {
    setSelectedCriteria(config);
    setShowCriteriaModal(true);
  };

  // const criteriaTypesOnClick: MenuProps["onClick"] = ({ key }) => {
  //   if (key === "uploadworkflow") {
  //     uploadWorkflow();
  //     return;
  //   }
  //   showWorkflow(sampleWorkflowConfig(key));
  // };

  return (
    <div className=" text-primary ">
      <CriteriaModal
        criteria={selectedCriteria}
        setCriteria={setSelectedCriteria}
        showModal={showCriteriaModal}
        setShowModal={setShowCriteriaModal}
        handler={(criteria: IAgentEvalCriteria) => {
          fetchCriteria();
        }}
      />
      {/*
      <WorkflowModal
        workflow={newCriteria}
        showModal={showNewWorkflowModal}
        setShowModal={setShowNewWorkflowModal}
        handler={(workflow: IAgentEvalCriteria) => {
          fetchCriteria();
        }}
      /> */}

      <div className="mb-2   relative">
        <div className="     rounded  ">
          <div className="flex mt-2 pb-2 mb-2 border-b">
            <div className="flex-1 font-semibold  mb-2 ">
              {" "}
              Criteria ({criteriaRows.length}){" "}
            </div>
            <div className=" ">
              <Dropdown.Button
                type="primary"
              //   menu={{ items: workflowTypes, onClick: criteriaTypesOnClick }}
                placement="bottomRight"
                trigger={["click"]}
                onClick={() => {
                  showCriteria({});
                }}
              >
                <PlusIcon className="w-5 h-5 inline-block mr-1" />
                Create Criteria
              </Dropdown.Button>
            </div>
          </div>
          <div className="text-xs mb-2 pb-1  ">
            {" "}
            Configure set of criteria for scoring workflow sessions.
          </div>
          {criteria_list && criteria_list.length > 0 && (
            <div
              // style={{ minHeight: "500px" }}
              className="w-full relative"
            >
              <LoadingOverlay loading={loading} />
              <ul className="flex flex-wrap gap-3">{criteriaRows}</ul>
            </div>
          )}
          {criteria_list && criteria_list.length === 0 && !loading && (
            <div className="text-sm border mt-4 rounded text-secondary p-2">
              <InformationCircleIcon className="h-4 w-4 inline mr-1" />
              No criteria found. Please create a new set of criteria.
            </div>
          )}
          {loading && (
            <div className="  w-full text-center">
              {" "}
              <BounceLoader />{" "}
              <span className="inline-block"> loading .. </span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
  
export default AgentEvalView;
  