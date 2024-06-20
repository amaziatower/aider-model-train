﻿using Dapr.Actors.Runtime;
using Dapr.Client;
using Microsoft.AI.Agents.Abstractions;

namespace Microsoft.AI.Agents.Dapr;

public abstract class Agent : Actor, IAgent
{
    private readonly DaprClient _daprClient;

    protected Agent(ActorHost host, DaprClient daprClient) : base(host)
    {
        this._daprClient = daprClient;
    }
    public abstract Task HandleEvent(Event item);

    public async Task PublishEvent(string ns, string id, Event item)
    {
        var metadata = new Dictionary<string, string>() {
                 { "cloudevent.Type", item.Type },
                 { "cloudevent.Subject",  item.Subject },
                 { "cloudevent.id", Guid.NewGuid().ToString()}
            };

        await _daprClient.PublishEventAsync(ns, id, item, metadata).ConfigureAwait(false);
    }
}
