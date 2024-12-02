// Copyright (c) Microsoft Corporation. All rights reserved.
// Client.cs

using Microsoft.Extensions.DependencyInjection;
using Microsoft.Extensions.Logging;

namespace Microsoft.AutoGen.Core;

/// <summary>
/// Represents a client agent that interacts with the AutoGen system.
/// </summary>
/// <param name="eventTypes">The event types associated with the client.</param>
/// <param name="logger">The logger instance for logging client activities.</param>
public sealed class Client([FromKeyedServices("EventTypes")] EventTypes eventTypes, ILogger<Client> logger)
    : Agent(eventTypes, logger)
{
}
