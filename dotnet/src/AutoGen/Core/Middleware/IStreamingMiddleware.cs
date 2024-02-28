﻿// Copyright (c) Microsoft Corporation. All rights reserved.
// IStreamingMiddleware.cs

using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace AutoGen.Core.Middleware;

/// <summary>
/// The streaming middleware interface
/// </summary>
public interface IStreamingMiddleware
{
    public string? Name { get; }

    public Task<IAsyncEnumerable<Message>> InvokeAsync(
        MiddlewareContext context,
        IStreamingAgent agent,
        CancellationToken cancellationToken = default);
}
