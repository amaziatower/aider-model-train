﻿// Copyright (c) Microsoft Corporation. All rights reserved.
// GroupChatManager.cs

using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;

namespace AutoGen;

public class GroupChatManager : IAgent
{
    public GroupChatManager(IGroupChat groupChat)
    {
        GroupChat = groupChat;
    }
    public string? Name => throw new ArgumentException("GroupChatManager does not have a name");

    public IChatLLM? ChatLLM => null;

    public IEnumerable<Message>? Messages { get; private set; }

    public IGroupChat GroupChat { get; }

    public async Task<Message> GenerateReplyAsync(
        IEnumerable<Message> messages,
        GenerateReplyOptions? options,
        CancellationToken cancellationToken = default)
    {
        var response = await GroupChat.CallAsync(messages, ct: cancellationToken);
        Messages = response;

        return response.Last();
    }
}
